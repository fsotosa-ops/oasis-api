# services/auth_service/api/v1/endpoints/auth.py
"""
Authentication endpoints.

Handles:
- User registration
- Login/logout
- Token refresh
- Password management
- Current user context (/me)
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from common.auth.security import get_current_user
from common.database.client import get_admin_client, get_supabase_client
from common.middleware import limit_auth
from common.schemas.logs import LogCategory
from services.auth_service.crud import log_user_action
from services.auth_service.schemas.auth import (
    LoginCredentials,
    PasswordResetRequest,
    PasswordUpdate,
    RefreshTokenRequest,
    TokenSchema,
    UserRegister,
    UserResponse,
)

router = APIRouter()
security = HTTPBearer()


# ============================================================================
# Registration
# ============================================================================


@router.post(
    "/register",
    response_model=TokenSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Create a new user account and return authentication tokens.",
    responses={429: {"description": "Rate limit excedido"}},
)
@limit_auth("10/minute")  # Strict limit to prevent mass registration
async def register(
    request: Request,
    user_in: UserRegister,
    db=Depends(get_supabase_client),  # noqa: B008
    admin_db=Depends(get_admin_client),  # noqa: B008
) -> Any:
    """
    Registra un nuevo usuario en Supabase Auth.

    El trigger `handle_new_user` en Supabase automáticamente:
    - Crea el perfil en `profiles`
    - Asigna membresía a la comunidad por defecto
    """
    try:
        auth_response = await db.auth.sign_up(
            {
                "email": user_in.email,
                "password": user_in.password,
                "options": {"data": {"full_name": user_in.full_name}},
            }
        )

        if not auth_response.session:
            # Email confirmation required
            raise HTTPException(
                status_code=status.HTTP_202_ACCEPTED,
                detail="Registration successful. Please confirm your email.",
            )

        # Log the registration (usa admin_db para bypass RLS en audit)
        await log_user_action(
            db=admin_db,
            user_id=auth_response.user.id,
            action="REGISTER",
            category=LogCategory.AUTH,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            metadata={"provider": "email", "full_name": user_in.full_name},
        )

        return {
            "access_token": auth_response.session.access_token,
            "refresh_token": auth_response.session.refresh_token,
            "expires_in": auth_response.session.expires_in,
            "token_type": "bearer",
            "user": auth_response.user.model_dump(),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ============================================================================
# Login
# ============================================================================


@router.post(
    "/login",
    response_model=TokenSchema,
    summary="Login",
    description="Authenticate with email and password, receive tokens.",
    responses={
        429: {"description": "Rate limit excedido - posible ataque de fuerza bruta"}
    },
)
@limit_auth("20/minute")  # Prevent brute force attacks
async def login(
    request: Request,
    credentials: LoginCredentials,
    db=Depends(get_supabase_client),  # noqa: B008
    admin_db=Depends(get_admin_client),  # noqa: B008
) -> Any:
    """
    Autentica credenciales contra Supabase Auth.

    Retorna tokens JWT nativos de Supabase.
    """
    try:
        auth_res = await db.auth.sign_in_with_password(
            {
                "email": credentials.email,
                "password": credentials.password,
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
        ) from e

    session = auth_res.session
    user = auth_res.user

    if not session or not user:
        raise HTTPException(status_code=401, detail="Authentication failed")

    # Log successful login (usa admin_db para bypass RLS en audit)
    await log_user_action(
        db=admin_db,
        user_id=user.id,
        action="LOGIN",
        category=LogCategory.AUTH,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "expires_in": session.expires_in,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "aud": getattr(user, "aud", "authenticated"),
        },
    }


# ============================================================================
# Token Refresh
# ============================================================================


@router.post(
    "/refresh",
    response_model=TokenSchema,
    summary="Refresh token",
    description="Get new access token using refresh token.",
)
async def refresh_session(
    refresh_req: RefreshTokenRequest,
    db=Depends(get_supabase_client),  # noqa: B008
) -> Any:
    """
    Renueva el Access Token usando el Refresh Token.
    """
    try:
        res = await db.auth.refresh_session(refresh_req.refresh_token)
        session = res.session

        if not session:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired refresh token",
            )

        return {
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "expires_in": session.expires_in,
            "token_type": "bearer",
            "user": res.user.model_dump(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail="Failed to refresh session",
        ) from e


# ============================================================================
# Logout
# ============================================================================


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout",
    description="Invalidate the current session.",
)
async def logout(
    request: Request,
    current_user: dict = Depends(get_current_user),  # noqa: B008
    db=Depends(get_supabase_client),  # noqa: B008
    admin_db=Depends(get_admin_client),  # noqa: B008
    token: HTTPAuthorizationCredentials = Depends(security),  # noqa: B008
) -> None:
    """
    Cierra la sesión actual.
    """
    # Log the logout
    await log_user_action(
        db=admin_db,
        user_id=current_user["id"],
        action="LOGOUT",
        category=LogCategory.AUTH,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    # Configurar contexto de usuario para sign_out
    db.postgrest.auth(token.credentials)
    await db.auth.sign_out()
    return None


# ============================================================================
# Current User Context
# ============================================================================


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Get the authenticated user's profile and organization memberships.",
)
async def read_users_me(
    current_user: dict = Depends(get_current_user),  # noqa: B008
    db=Depends(get_supabase_client),  # noqa: B008
    token: HTTPAuthorizationCredentials = Depends(security),  # noqa: B008
) -> Any:
    """
    Obtiene el perfil completo del usuario actual incluyendo sus membresías.

    Este endpoint es esencial para que el frontend sepa:
    - Quién es el usuario
    - Si es Platform Admin
    - A qué organizaciones pertenece y con qué rol

    Defensa en profundidad:
    - Backend verifica identidad via get_current_user
    - RLS verifica que solo accede a sus propios datos
    """
    # Configurar RLS con el contexto del usuario
    db.postgrest.auth(token.credentials)

    user_id = current_user["id"]

    try:
        # Query de perfil - RLS asegura que solo veo mi perfil
        profile_res = (
            await db.table("profiles")
            .select(
                "id, email, full_name, avatar_url, is_platform_admin,"
                "metadata, created_at, updated_at"
            )
            .eq("id", user_id)
            .single()
            .execute()
        )

        if not profile_res.data:
            raise HTTPException(status_code=404, detail="Profile not found")

        # Query de membresías - RLS asegura que solo veo mis membresías
        memberships_res = (
            await db.table("organization_members")
            .select(
                "role, status, joined_at, "
                "organizations(id, name, slug, type, settings, created_at)"
            )
            .eq("user_id", user_id)
            .eq("status", "active")
            .execute()
        )

        # Formatear membresías
        formatted_memberships = []
        for m in memberships_res.data or []:
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

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching profile: {e}"
        ) from e


# ============================================================================
# Password Management
# ============================================================================


@router.post(
    "/password/reset-request",
    status_code=status.HTTP_200_OK,
    summary="Request password reset",
    description="Send password reset email to the user.",
    responses={429: {"description": "Rate limit excedido"}},
)
@limit_auth("5/minute")  # Very strict to prevent email spam
async def request_password_reset(
    request: Request,
    payload: PasswordResetRequest,
    db=Depends(get_supabase_client),  # noqa: B008
) -> Any:
    """
    Inicia el flujo de recuperación de contraseña.

    Supabase envía el email con el link de reset.
    La respuesta es siempre exitosa para evitar enumeración de usuarios.
    """
    try:
        await db.auth.reset_password_email(payload.email)
    except Exception:
        # Silent failure to prevent user enumeration
        pass

    return {"message": "If the email exists, you will receive reset instructions."}


@router.post(
    "/password/update",
    status_code=status.HTTP_200_OK,
    summary="Update password",
    description="Change password using a valid session token.",
)
async def update_password(
    payload: PasswordUpdate,
    token: HTTPAuthorizationCredentials = Depends(security),  # noqa: B008
    db=Depends(get_supabase_client),  # noqa: B008
    admin_db=Depends(get_admin_client),  # noqa: B008
) -> Any:
    """
    Actualiza la contraseña del usuario.

    Requiere un token válido (de login o del link de reset).
    """
    try:
        # Verify the token is valid
        user_response = await db.auth.get_user(token.credentials)

        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        user_id = user_response.user.id

        # Update password using admin client (necesario para cambiar password)
        await admin_db.auth.admin.update_user_by_id(
            user_id,
            {"password": payload.new_password},
        )

        # Log the password change
        await log_user_action(
            db=admin_db,
            user_id=user_id,
            action="PASSWORD_CHANGE",
            category=LogCategory.AUTH,
            metadata={"method": "manual_update"},
        )

        return {"message": "Password updated successfully."}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail="Failed to update password.",
        ) from e
