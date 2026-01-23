from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# --- Base Schemas ---
class OrganizationBase(BaseModel):
    name: str = Field(..., example="Banco Estado")
    slug: str = Field(..., example="banco-estado")
    type: str = Field(
        ..., description="'sponsor', 'provider' o 'community'", example="sponsor"
    )
    settings: dict[str, Any] = Field(default_factory=dict)


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationOut(OrganizationBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


# --- Member Schemas ---
class MemberAdd(BaseModel):
    """Esquema para invitar/agregar un miembro"""

    email: EmailStr
    role: str = Field(
        ...,
        description="'admin', 'facilitador', 'participante'",
        example="participante",
    )


class MembershipOut(BaseModel):
    """Esquema para devolver la membresía completa en /me"""

    role: str
    status: str
    joined_at: datetime
    organization: OrganizationOut  # Anidamos la info de la org

    class Config:
        from_attributes = True
