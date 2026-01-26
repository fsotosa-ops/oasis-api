class ErrorCodes:
    """
    Catálogo centralizado de errores de negocio.
    Evita usar strings mágicos dispersos por el código.
    """

    # General
    INTERNAL_ERROR = "sys_001"
    UNAUTHORIZED = "auth_001"

    # Journeys
    JOURNEY_NOT_FOUND = "journey_001"
    ENROLLMENT_ALREADY_EXISTS = "journey_002"
    STEP_LOCKED = "journey_003"
    USER_NOT_IN_ORG = "journey_004"

    # Webhooks
    INVALID_SIGNATURE = "webhook_001"
    PROVIDER_NOT_FOUND = "webhook_002"
    PROVIDER_NOT_CONFIGURED = "webhook_003"
    INVALID_PAYLOAD = "webhook_004"
    EVENT_ALREADY_PROCESSED = "webhook_005"
