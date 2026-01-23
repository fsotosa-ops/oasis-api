from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserAdminOut(BaseModel):
    """Esquema detallado para la gestión global de usuarios."""

    id: UUID
    email: EmailStr
    full_name: str | None = None
    avatar_url: str | None = None
    is_platform_admin: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class UserPlatformAdminUpdate(BaseModel):
    is_platform_admin: bool
