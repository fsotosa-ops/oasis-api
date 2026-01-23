from typing import Any

from pydantic import BaseModel, EmailStr, Field


class ProfileOut(BaseModel):
    """
    El 'Pasaporte' del usuario.
    Este modelo es seguro y compartido por todos los microservicios.
    """

    id: str
    email: EmailStr
    role: str
    metadata: dict[str, Any] | None = Field(default_factory=dict)

    class Config:
        from_attributes = True
