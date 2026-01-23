from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

# --- Imports Comunes ---
from common.auth.security import get_current_user
from common.database.client import get_admin_client, get_supabase_client
from common.schemas.logs import LogCategory

# --- Imports Locales ---
from services.auth_service.crud.audit import log_user_action
from services.auth_service.schemas.auth import (
    LoginCredentials,
    RefreshTokenRequest,
    TokenSchema,
    UserRegister,
    UserResponse,
)

router = APIRouter()


# -----------------------------------------------------------------------------
# 1. Registro de Usuario
# -----------------------------------------------------------------------------
@router.post(
    "/register", response_model=TokenSchema, status_code=status.HTTP_201_CREATED
)
async def register(
    user_in: UserRegister,
    request: Request,
    db=Depends(get_supabase_client),  # noqa: B008
    admin_db=Depends(get_admin_client),  # noqa: B008
) -> Any:
    """
    Registra un nuevo usuario en Supabase Auth y crea su entrada en auditoría.
    """
    try:
        # A. Crear usuario en Supabase
        # Pasamos full_name en la metadata para que el trigger handle_new_user lo use
        auth_response = await db.auth.sign_up(
            {
                "email": user_in.email,
                "password": user_in.password,
                "options": {"data": {"full_name": user_in.full_name}},
            }
        )

        if not auth_response.session:
            # Si Supabase requiere confirmación de correo, no devuelve sesión inmediata
            raise HTTPException(
                status_code=status.HTTP_202_ACCEPTED,
                detail="Usuario registrado. Por favor confirma tu correo electrónico.",
            )

        # B. Registrar Auditoría
        await log_user_action(
            db=admin_db,
            user_id=auth_response.user.id,
            action="REGISTER",
            category=LogCategory.AUTH,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            metadata={"provider": "email", "full_name": user_in.full_name},
        )

        # C. Retornar Tokens
        return {
            "access_token": auth_response.session.access_token,
            "refresh_token": auth_response.session.refresh_token,
            "expires_in": auth_response.session.expires_in,
            "token_type": "bearer",
            "user": auth_response.user.model_dump(),
        }

    except Exception as e:
        print(f"❌ Register Error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e)) from e


# -----------------------------------------------------------------------------
# 2. Login (Proxy a Supabase)
# -----------------------------------------------------------------------------
@router.post("/login", response_model=TokenSchema)
async def login(
    credentials: LoginCredentials,
    request: Request,
    db=Depends(get_supabase_client),  # noqa: B008
    admin_db=Depends(get_admin_client),  # noqa: B008
) -> Any:
    """
    Autentica credenciales contra Supabase y devuelve los tokens originales.
    """
    try:
        # A. Autenticar con Supabase
        auth_res = await db.auth.sign_in_with_password(
            {"email": credentials.email, "password": credentials.password}
        )
    except Exception as e:
        print(f"❌ Login Error (Supabase): {str(e)}")
        raise HTTPException(status_code=401, detail="Credenciales incorrectas") from e

    session = auth_res.session
    user = auth_res.user

    if not session or not user:
        raise HTTPException(status_code=401, detail="Error obteniendo sesión")

    # B. Registrar Auditoría
    try:
        await log_user_action(
            db=admin_db,
            user_id=user.id,
            action="LOGIN",
            category=LogCategory.AUTH,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
        )
    except Exception as e:
        print(f"⚠️ Warning: Falló el log de login: {e}")
        raise HTTPException(status_code=401, detail="Credenciales incorrectas") from e

    # C. Retornar Tokens Nativos de Supabase
    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "expires_in": session.expires_in,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            # Aseguramos que 'aud' exista, aunque sea por defecto
            "aud": getattr(user, "aud", "authenticated"),
        },
    }


# -----------------------------------------------------------------------------
# 3. Refresh Token
# -----------------------------------------------------------------------------
@router.post("/refresh", response_model=TokenSchema)
async def refresh_session(
    refresh_req: RefreshTokenRequest,
    db=Depends(get_supabase_client),  # noqa: B008
) -> Any:
    """
    Renueva el Access Token usando el Refresh Token de Supabase.
    """
    try:
        res = await db.auth.refresh_session(refresh_req.refresh_token)
        session = res.session

        if not session:
            raise HTTPException(
                status_code=401, detail="Refresh token inválido o expirado"
            )

        return {
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "expires_in": session.expires_in,
            "token_type": "bearer",
            "user": res.user.model_dump(),
        }
    except Exception as e:
        print(f"❌ Refresh Error: {str(e)}")
        raise HTTPException(
            status_code=401, detail="No se pudo refrescar la sesión"
        ) from e


# -----------------------------------------------------------------------------
# 4. Logout
# -----------------------------------------------------------------------------
@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    db=Depends(get_supabase_client),  # noqa: B008
    current_user: dict = Depends(get_current_user),  # noqa: B008
    admin_db=Depends(get_admin_client),  # noqa: B008
) -> None:
    """
    Cierra la sesión (invalida el token en el lado del servidor Supabase).
    """
    # A. Registrar Salida
    await log_user_action(
        db=admin_db,
        user_id=current_user["id"],
        action="LOGOUT",
        category=LogCategory.AUTH,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
    )

    # B. Sign Out en Supabase
    await db.auth.sign_out()
    return None


# -----------------------------------------------------------------------------
# 5. Get Me (Perfil + Contexto Multi-Tenant)
# -----------------------------------------------------------------------------
@router.get("/me", response_model=UserResponse)
async def read_users_me(
    current_user: dict = Depends(get_current_user),  # noqa: B008
    db=Depends(get_supabase_client),  # noqa: B008
) -> Any:
    """
    Obtiene la identidad del usuario y sus contextos (membresías).
    Esencial para que el Frontend sepa qué organizaciones mostrar.
    """
    user_id = current_user["id"]

    # A. Obtener Perfil Base
    profile_res = (
        await db.table("profiles").select("*").eq("id", user_id).single().execute()
    )
    if not profile_res.data:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")

    # B. Obtener Membresías con JOIN a Organizaciones
    memberships_res = (
        await db.table("organization_members")
        .select(
            "role, status, joined_at, organizations(id, name, slug, type, settings)"
        )
        .eq("user_id", user_id)
        .execute()
    )

    # C. Formatear respuesta (Aplanar estructura)
    formatted_memberships = []
    if memberships_res.data:
        for m in memberships_res.data:
            # Validamos que la relación exista (por si la org fue borrada físicamente)
            if m.get("organizations"):
                formatted_memberships.append(
                    {
                        "role": m["role"],
                        "status": m["status"],
                        "joined_at": m["joined_at"],
                        "organization": m["organizations"],
                    }
                )

    return {**profile_res.data, "memberships": formatted_memberships}
