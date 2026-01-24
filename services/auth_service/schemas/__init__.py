# services/auth_service/schemas/__init__.py
"""
Pydantic schemas for auth_service.
"""
from services.auth_service.schemas.audit import (
    AuditCategoryOut,
    AuditLogOut,
    PaginatedAuditLogsResponse,
)
from services.auth_service.schemas.auth import (
    LoginCredentials,
    PasswordResetRequest,
    PasswordUpdate,
    RefreshTokenRequest,
    TokenSchema,
    UserRegister,
    UserResponse,
    UserUpdate,
)
from services.auth_service.schemas.organizations import (
    MemberAdd,
    MemberRoleUpdate,
    MembershipOut,
    MembershipWithOrg,
    MemberUserInfo,
    OrganizationCreate,
    OrganizationDetailOut,
    OrganizationOut,
    OrganizationUpdate,
    OrganizationWithRole,
    OwnershipTransfer,
    PaginatedMembersResponse,
    PaginatedOrganizationsResponse,
)
from services.auth_service.schemas.users import (
    PaginatedUsersResponse,
    UserAdminOut,
    UserBase,
    UserCreate,
    UserDetailOut,
    UserMemberOut,
    UserPlatformAdminUpdate,
    UserPublicOut,
)

__all__ = [
    # Auth
    "LoginCredentials",
    "PasswordResetRequest",
    "PasswordUpdate",
    "RefreshTokenRequest",
    "TokenSchema",
    "UserRegister",
    "UserResponse",
    "UserUpdate",
    # Audit
    "AuditCategoryOut",
    "AuditLogOut",
    "PaginatedAuditLogsResponse",
    # Organizations
    "MemberAdd",
    "MemberRoleUpdate",
    "MembershipOut",
    "MembershipWithOrg",
    "MemberUserInfo",
    "OrganizationCreate",
    "OrganizationDetailOut",
    "OrganizationOut",
    "OrganizationUpdate",
    "OrganizationWithRole",
    "OwnershipTransfer",
    "PaginatedMembersResponse",
    "PaginatedOrganizationsResponse",
    # Users
    "PaginatedUsersResponse",
    "UserAdminOut",
    "UserBase",
    "UserCreate",
    "UserDetailOut",
    "UserMemberOut",
    "UserPlatformAdminUpdate",
    "UserPublicOut",
]
