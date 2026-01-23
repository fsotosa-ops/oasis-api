from common.config import Settings as CommonSettings


class AuthSettings(CommonSettings):
    PROJECT_NAME: str = "Oasis Auth Service"
    # Aquí podrías agregar configuraciones únicas para Auth si las tuvieras
    # Ejemplo:
    # PASSWORD_MIN_LENGTH: int = 8


settings = AuthSettings()
