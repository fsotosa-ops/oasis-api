# services/auth_service/schemas/users.py
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserAdminOut(BaseModel):
    """Esquema detallado para la gestión de usuarios por un Administrador."""

    id: UUID
    email: EmailStr
    full_name: str | None = None
    avatar_url: str | None = None
    is_platform_admin: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserPlatformAdminUpdate(BaseModel):
    """Esquema para actualizar el estatus de administrador de plataforma."""

    is_platform_admin: bool
