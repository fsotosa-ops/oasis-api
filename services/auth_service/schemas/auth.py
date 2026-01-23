from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr

# Importamos el esquema de membresías local
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


# 2. Perfil Multi-Tenant (Lo que devuelve /me)
class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str | None = None
    avatar_url: str | None = None
    is_platform_admin: bool = False

    # Lista de contextos (Donde el usuario es miembro)
    memberships: list[MembershipOut] = []

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    full_name: str | None = None
    avatar_url: str | None = None
    metadata: dict[str, Any] | None = None
