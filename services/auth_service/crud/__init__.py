# services/auth_service/crud/__init__.py
"""
CRUD operations for auth_service.
Each module handles a specific domain.
"""
from services.auth_service.crud.audit import (
    AuditOperationError,
    get_audit_categories,
    get_organization_activity,
    get_user_activity,
    list_audit_logs,
    log_user_action,
)
from services.auth_service.crud.organizations import (
    MembershipExistsError,
    MembershipNotFoundError,
    MembershipOperationError,
    OrganizationExistsError,
    OrganizationNotFoundError,
    OrganizationOperationError,
    add_member,
    count_owners,
    create_organization,
    delete_organization,
    get_membership,
    get_organization_by_id,
    get_organization_by_slug,
    list_all_organizations,
    list_organization_members,
    list_user_organizations,
    remove_member,
    transfer_ownership,
    update_membership,
    update_organization,
)
from services.auth_service.crud.profiles import (
    ProfileNotFoundError,
    ProfileOperationError,
    delete_user_completely,
    get_profile_by_email,
    get_profile_by_id,
    get_user_with_memberships,
    list_all_profiles,
    set_platform_admin_status,
    update_profile,
)

__all__ = [
    # Profiles
    "ProfileNotFoundError",
    "ProfileOperationError",
    "get_profile_by_id",
    "get_profile_by_email",
    "list_all_profiles",
    "update_profile",
    "set_platform_admin_status",
    "delete_user_completely",
    "get_user_with_memberships",
    # Organizations
    "OrganizationNotFoundError",
    "OrganizationExistsError",
    "OrganizationOperationError",
    "get_organization_by_id",
    "get_organization_by_slug",
    "list_all_organizations",
    "list_user_organizations",
    "create_organization",
    "update_organization",
    "delete_organization",
    # Memberships
    "MembershipNotFoundError",
    "MembershipExistsError",
    "MembershipOperationError",
    "get_membership",
    "list_organization_members",
    "add_member",
    "update_membership",
    "remove_member",
    "count_owners",
    "transfer_ownership",
    # Audit
    "AuditOperationError",
    "log_user_action",
    "list_audit_logs",
    "get_user_activity",
    "get_organization_activity",
    "get_audit_categories",
]
