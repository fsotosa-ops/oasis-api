from fastapi import APIRouter, Depends, HTTPException, Request, status

# Imports de Common (Lo compartido)
from common.auth.security import get_current_user
from common.database.client import get_admin_client, get_supabase_client
from common.schemas.auth import ProfileOut
from services.auth_service.crud.audit import log_user_action

# Imports Locales del Microservicio (La nueva estructura)
from services.auth_service.schemas.auth import (
    LoginCredentials,
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
    request: Request,
    db=Depends(get_supabase_client),  # noqa: B008
    admin_db=Depends(get_admin_client),  # noqa: B008
):
    try:
        auth_response = await db.auth.sign_up(
            {
                "email": user_in.email,
                "password": user_in.password,
                "options": {"data": {"full_name": user_in.full_name}},
            }
        )

        if not auth_response.session:
            raise HTTPException(
                status_code=status.HTTP_202_ACCEPTED,
                detail="Usuario registrado. Por favor confirma tu correo.",
            )

        # Usamos el CRUD local para el log
        await log_user_action(
            db=admin_db,
            user_id=auth_response.user.id,
            action="REGISTER",
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            metadata={"provider": "email", "full_name": user_in.full_name},
        )

        return {
            "access_token": auth_response.session.access_token,
            "refresh_token": auth_response.session.refresh_token,
            "expires_in": auth_response.session.expires_in,
            "user": auth_response.user.model_dump(),
        }

    except Exception as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post("/login", response_model=TokenSchema)
async def login(
    credentials: LoginCredentials,
    request: Request,
    db=Depends(get_supabase_client),  # noqa: B008
    admin_db=Depends(get_admin_client),  # noqa: B008
):
    try:
        response = await db.auth.sign_in_with_password(
            {"email": credentials.email, "password": credentials.password}
        )

        if not response.session:
            raise HTTPException(status_code=400, detail="Error al iniciar sesión")

        # Usamos el CRUD local para el log
        await log_user_action(
            db=admin_db,
            user_id=response.user.id,
            action="LOGIN",
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            metadata={"method": "password"},
        )

        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "expires_in": response.session.expires_in,
            "user": response.user.model_dump(),
        }
    except Exception as err:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas") from err


@router.post("/refresh", response_model=TokenSchema)
async def refresh_token(
    body: RefreshTokenRequest, db=Depends(get_supabase_client)  # noqa: B008
):
    try:
        response = await db.auth.refresh_session(body.refresh_token)
        if not response.session:
            raise HTTPException(status_code=401, detail="Sesión inválida")

        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "expires_in": response.session.expires_in,
            "user": response.user.model_dump(),
        }
    except Exception as err:
        raise HTTPException(status_code=401, detail="Refresh token inválido") from err


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    db=Depends(get_supabase_client),  # noqa: B008
    current_user: dict = Depends(get_current_user),  # noqa: B008
    admin_db=Depends(get_admin_client),  # noqa: B008
):
    # Log de salida
    await log_user_action(
        db=admin_db,
        user_id=current_user["id"],
        action="LOGOUT",
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
    )
    await db.auth.sign_out()
    return None


@router.get("/me", response_model=ProfileOut)
async def read_users_me(current_user: dict = Depends(get_current_user)):  # noqa: B008
    return current_user
