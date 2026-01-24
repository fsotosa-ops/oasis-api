# services/auth_service/schemas/audit.py
"""
Pydantic schemas for audit logs.
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AuditLogOut(BaseModel):
    """Schema for audit log output."""

    id: str
    actor_id: str | None = None
    actor_email: str | None = None
    organization_id: str | None = None
    category_code: str
    action: str
    resource: str | None = None
    resource_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    ip_address: str | None = None
    user_agent: str | None = None
    occurred_at: datetime

    class Config:
        from_attributes = True


class AuditCategoryOut(BaseModel):
    """Schema for audit category output."""

    code: str
    name: str
    description: str | None = None

    class Config:
        from_attributes = True


class PaginatedAuditLogsResponse(BaseModel):
    """Paginated response for audit logs."""

    items: list[AuditLogOut]
    total: int
    skip: int
    limit: int
