from functools import lru_cache

from common.config import CommonSettings


class JourneySettings(CommonSettings):
    """
    Journey Service specific settings.
    Inherits all common settings (Supabase, JWT, etc.) from CommonSettings.
    """

    PROJECT_NAME: str = "OASIS Journey Service"

    # Journey-specific settings
    TYPEFORM_SECRET: str = ""

    # Gamification defaults (can be overridden per org)
    DEFAULT_POINTS_SOCIAL_POST: int = 5
    DEFAULT_POINTS_VIDEO_VIEW: int = 3
    DEFAULT_POINTS_RESOURCE_VIEW: int = 2


@lru_cache
def get_settings() -> JourneySettings:
    return JourneySettings()


settings = get_settings()
