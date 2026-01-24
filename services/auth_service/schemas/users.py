# services/auth_service/schemas/users.py
"""
Pydantic schemas for user management.
"""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from services.auth_service.schemas.organizations import MembershipWithOrg

# ============================================================================
# Base Schemas
# ============================================================================


class UserBase(BaseModel):
    """Base user fields."""

    email: EmailStr
    full_name: str | None = None
    avatar_url: str | None = None


class UserCreate(UserBase):
    """Schema for creating a user (registration)."""

    password: str = Field(..., min_length=6)


# ============================================================================
# Output Schemas
# ============================================================================


class UserAdminOut(BaseModel):
    """Schema for admin view of users."""

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


class UserDetailOut(UserAdminOut):
    """Schema for detailed user view including memberships."""

    memberships: list[MembershipWithOrg] = []


class UserPublicOut(BaseModel):
    """Public user information (for other users to see)."""

    id: UUID
    email: EmailStr
    full_name: str | None = None
    avatar_url: str | None = None

    class Config:
        from_attributes = True


class UserMemberOut(BaseModel):
    """User info as seen in membership context."""

    id: UUID
    email: EmailStr
    full_name: str | None = None
    avatar_url: str | None = None
    org_role: str | None = None
    membership_status: str | None = None
    joined_at: datetime | None = None

    class Config:
        from_attributes = True


# ============================================================================
# Update Schemas
# ============================================================================


class UserUpdate(BaseModel):
    """Schema for updating user profile."""

    full_name: str | None = None
    avatar_url: str | None = None
    metadata: dict[str, Any] | None = None


class UserPlatformAdminUpdate(BaseModel):
    """Schema for updating platform admin status."""

    is_platform_admin: bool


# ============================================================================
# Paginated Response
# ============================================================================


class PaginatedUsersResponse(BaseModel):
    """Paginated list of users."""

    items: list[UserAdminOut]
    total: int
    skip: int
    limit: int
