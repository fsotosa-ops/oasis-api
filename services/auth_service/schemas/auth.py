from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr

from .organizations import MembershipOut


# 1. Auth & Tokens
class LoginCredentials(BaseModel):
    email: EmailStr
    password: str


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenSchema(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict[str, Any]


# 2. Gestión de Contraseñas (NUEVO)
class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordUpdate(BaseModel):
    new_password: str


# 3. Perfil Multi-Tenant
class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str | None = None
    avatar_url: str | None = None
    is_platform_admin: bool = False
    memberships: list[MembershipOut] = []

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    full_name: str | None = None
    avatar_url: str | None = None
    metadata: dict[str, Any] | None = None
