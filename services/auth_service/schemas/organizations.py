# services/auth_service/schemas/organizations.py
"""
Pydantic schemas for organization and membership management.
"""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator

# ============================================================================
# Organization Schemas
# ============================================================================


class OrganizationBase(BaseModel):
    """Base organization fields."""

    name: str = Field(..., min_length=2, max_length=100, example="Banco Estado")
    slug: str = Field(
        ...,
        min_length=2,
        max_length=50,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        example="banco-estado",
        description="URL-friendly identifier (lowercase, hyphens only)",
    )
    type: str = Field(
        default="sponsor",
        description="Organization type: 'sponsor', 'provider', or 'community'",
        example="sponsor",
    )
    settings: dict[str, Any] = Field(default_factory=dict)


class OrganizationCreate(OrganizationBase):
    """Schema for creating an organization."""

    pass


class OrganizationUpdate(BaseModel):
    """Schema for updating an organization. Only updatable fields."""

    name: str | None = Field(None, min_length=2, max_length=100)
    settings: dict[str, Any] | None = None


class OrganizationOut(OrganizationBase):
    """Standard organization output."""

    id: UUID
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class OrganizationDetailOut(OrganizationOut):
    """Detailed organization output with member count."""

    member_count: int = 0


class OrganizationWithRole(OrganizationOut):
    """Organization with the user's role in it."""

    membership_role: str
    membership_status: str
    joined_at: datetime | None = None


# ============================================================================
# Member/User Schemas (for nested responses)
# ============================================================================


class MemberUserInfo(BaseModel):
    """Basic user info for membership responses."""

    id: UUID
    email: EmailStr
    full_name: str | None = None
    avatar_url: str | None = None

    class Config:
        from_attributes = True


# ============================================================================
# Membership Schemas
# ============================================================================


class MemberAdd(BaseModel):
    """Schema for adding a member to an organization.

    Provide either email OR user_id (not both).
    - email: For inviting by email (typical UI flow)
    - user_id: For programmatic operations where you have the ID
    """

    email: EmailStr | None = Field(None, description="Email of the user to invite")
    user_id: str | None = Field(None, description="UUID of the user to add")
    role: str = Field(
        default="participante",
        description="Role to assign: 'owner', 'admin', 'facilitador', 'participante'",
        example="participante",
    )

    @model_validator(mode="after")
    def check_email_or_user_id(self):
        """Ensure exactly one of email or user_id is provided."""
        if not self.email and not self.user_id:
            raise ValueError("Either 'email' or 'user_id' must be provided")
        if self.email and self.user_id:
            raise ValueError("Provide either 'email' or 'user_id', not both")
        return self


class MemberRoleUpdate(BaseModel):
    """Schema for updating a member's role."""

    role: str = Field(
        ...,
        description="New role: 'owner', 'admin', 'facilitador', 'participante'",
        example="admin",
    )


class MembershipOut(BaseModel):
    """Output schema for a membership."""

    user_id: UUID
    role: str
    status: str
    joined_at: datetime | None = None
    user: MemberUserInfo | None = None

    class Config:
        from_attributes = True


class MembershipWithOrg(BaseModel):
    """Membership with full organization data (used in /me endpoint)."""

    role: str
    status: str
    joined_at: datetime | None = None
    organization: OrganizationOut

    class Config:
        from_attributes = True


class OwnershipTransfer(BaseModel):
    """Schema for transferring organization ownership."""

    new_owner_id: str = Field(
        ...,
        description="UUID of the member who will become the new owner",
    )


# ============================================================================
# Paginated Responses
# ============================================================================


class PaginatedOrganizationsResponse(BaseModel):
    """Paginated list of organizations."""

    items: list[OrganizationOut]
    total: int
    skip: int
    limit: int


class PaginatedMembersResponse(BaseModel):
    """Paginated list of members."""

    items: list[MembershipOut]
    total: int
    skip: int
    limit: int
