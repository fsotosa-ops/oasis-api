from fastapi import APIRouter, Depends, HTTPException, status

from common.auth.security import get_current_user
from common.database.client import get_supabase_client
from common.schemas.auth import (
    LoginCredentials,
    ProfileOut,
    RefreshTokenRequest,
    TokenSchema,
    UserRegister,
)

router = APIRouter()


@router.post(
    "/register", response_model=TokenSchema, status_code=status.HTTP_201_CREATED
)
async def register(
    user_in: UserRegister,
    db=Depends(get_supabase_client),  # noqa: B008
):
    """
    Registra un nuevo usuario (Rol por defecto: 'visitante').
    Devuelve la sesión iniciada inmediatamente.
    """
    try:
        # 1. Crear usuario en Auth (Supabase GoTrue)
        # El trigger en BD se encargará de crear el perfil en public.profiles
        auth_response = await db.auth.sign_up(
            {
                "email": user_in.email,
                "password": user_in.password,
                "options": {"data": {"full_name": user_in.full_name}},
            }
        )

        if not auth_response.session:
            # Caso: Confirmación de email requerida
            raise HTTPException(
                status_code=status.HTTP_202_ACCEPTED,
                detail="Usuario registrado. Por favor confirma tu correo.",
            )

        return {
            "access_token": auth_response.session.access_token,
            "refresh_token": auth_response.session.refresh_token,
            "expires_in": auth_response.session.expires_in,
            "user": auth_response.user.model_dump(),
        }

    except Exception as err:
        # B904: Explicitly chain the exception
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)
        ) from err


@router.post("/login", response_model=TokenSchema)
async def login(
    credentials: LoginCredentials,
    db=Depends(get_supabase_client),  # noqa: B008
):
    """Inicio de sesión para obtener Access y Refresh Tokens."""
    try:
        response = await db.auth.sign_in_with_password(
            {"email": credentials.email, "password": credentials.password}
        )

        if not response.session:
            raise HTTPException(status_code=400, detail="Error al iniciar sesión")

        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "expires_in": response.session.expires_in,
            "user": response.user.model_dump(),
        }
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas"
        ) from err


@router.post("/refresh", response_model=TokenSchema)
async def refresh_token(
    body: RefreshTokenRequest,
    db=Depends(get_supabase_client),  # noqa: B008
):
    """Obtiene un nuevo Access Token usando el Refresh Token."""
    try:
        response = await db.auth.refresh_session(body.refresh_token)

        if not response.session:
            raise HTTPException(status_code=401, detail="Sesión inválida o expirada")

        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "expires_in": response.session.expires_in,
            "user": response.user.model_dump(),
        }
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido"
        ) from err


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(db=Depends(get_supabase_client)):  # noqa: B008
    """Cierra la sesión del lado del servidor."""
    await db.auth.sign_out()
    return None


@router.get("/me", response_model=ProfileOut)
async def read_users_me(
    current_user: dict = Depends(get_current_user),  # noqa: B008
):
    """Retorna el perfil del habitante autenticado (incluyendo rol)."""
    return current_user
