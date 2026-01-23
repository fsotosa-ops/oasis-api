from typing import Any

from pydantic import BaseModel, EmailStr, Field


class ProfileOut(BaseModel):
    id: str
    email: EmailStr
    role: str
    metadata: dict[str, Any] | None = Field(default_factory=dict)

    class Config:
        from_attributes = True


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class TokenSchema(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict  # Información básica del usuario retornada por Supabase


class LoginCredentials(BaseModel):
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str
