from pydantic import BaseModel, EmailStr

# --- Modelos de Entrada (Request) ---


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class LoginCredentials(BaseModel):
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# --- Modelos de Salida (Response) ---


class TokenSchema(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict  # Datos crudos del usuario de Supabase
