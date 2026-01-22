from enum import Enum


class LogCategory(str, Enum):
    AUTH = "auth"
    PROFILE = "profile"
    BILLING = "billing"
    SYSTEM = "system"
