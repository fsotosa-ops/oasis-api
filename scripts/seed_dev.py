#!/usr/bin/env python3
"""
Development Seed Script for OASIS Platform.

This script creates test data by calling the actual API endpoints,
which generates real audit logs just like production usage.

REQUIRES: API must be running (uvicorn services.auth_service.main:app)

Usage:
    python scripts/seed_dev.py              # Full seed
    python scripts/seed_dev.py --clean      # Clean and reseed
    python scripts/seed_dev.py --api-url http://localhost:8001  # Custom API URL

Requirements:
    - API running at localhost:8000 (or specify --api-url)
    - SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env (for admin operations)
"""
import argparse
import os
import sys
from dataclasses import dataclass, field

import httpx
from dotenv import load_dotenv

from supabase import Client, create_client

# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_API_URL = "http://localhost:8000/api/v1"
DEFAULT_PASSWORD = "Test123!"


@dataclass
class OrgConfig:
    """Organization configuration."""

    name: str
    slug: str
    org_type: str
    description: str = ""
    settings: dict = field(default_factory=dict)


@dataclass
class UserConfig:
    """User configuration."""

    email: str
    full_name: str
    password: str = DEFAULT_PASSWORD
    is_platform_admin: bool = False
    memberships: list = field(default_factory=list)  # List of (org_slug, role)


# =============================================================================
# SEED DATA
# =============================================================================

DEV_ORGANIZATIONS = [
    OrgConfig(
        name="Fundación Summer",
        slug="fundacion-summer",
        org_type="provider",
        description="Organización proveedora de experiencias de bienestar",
        settings={"theme": "summer", "features": ["admin_panel", "analytics"]},
    ),
    OrgConfig(
        name="Banco Demo B2B",
        slug="banco-demo",
        org_type="sponsor",
        description="Cliente corporativo demo",
        settings={"theme": "corporate_blue", "features": ["reports", "bulk_invite"]},
    ),
    OrgConfig(
        name="Startup Tech",
        slug="startup-tech",
        org_type="enterprise",
        description="Empresa tecnológica demo",
        settings={"features": ["api_access"]},
    ),
]

DEV_USERS = [
    # Platform Admin (God mode) - MUST BE FIRST
    UserConfig(
        email="admin@oasis.dev",
        full_name="Platform Admin",
        is_platform_admin=True,
        memberships=[("fundacion-summer", "owner")],
    ),
    # Organization Owner
    UserConfig(
        email="owner@summer.dev",
        full_name="María García (Owner)",
        memberships=[("fundacion-summer", "owner")],
    ),
    # Organization Admin
    UserConfig(
        email="admin@summer.dev",
        full_name="Carlos López (Admin)",
        memberships=[("fundacion-summer", "admin")],
    ),
    # Facilitador (multiple orgs)
    UserConfig(
        email="facilitador@summer.dev",
        full_name="Laura Martínez (Facilitador)",
        memberships=[
            ("fundacion-summer", "facilitador"),
            ("banco-demo", "facilitador"),
        ],
    ),
    # Regular participants
    UserConfig(
        email="participante1@banco.dev",
        full_name="Juan Pérez",
        memberships=[("banco-demo", "participante")],
    ),
    UserConfig(
        email="participante2@banco.dev",
        full_name="Ana Rodríguez",
        memberships=[("banco-demo", "participante")],
    ),
    # User with multiple roles
    UserConfig(
        email="multi@oasis.dev",
        full_name="Pedro Sánchez (Multi-Org)",
        memberships=[
            ("fundacion-summer", "participante"),
            ("banco-demo", "admin"),
            ("startup-tech", "owner"),
        ],
    ),
    # User without explicit memberships (only community)
    UserConfig(
        email="visitante@gmail.dev",
        full_name="Visitor User",
        memberships=[],
    ),
]


# =============================================================================
# SEEDER CLASS
# =============================================================================


class DevSeeder:
    """Seeds development data using API endpoints."""

    def __init__(self, api_url: str, supabase_url: str, service_role_key: str):
        self.api_url = api_url.rstrip("/")
        self.supabase: Client = create_client(supabase_url, service_role_key)
        self.http = httpx.Client(timeout=30.0)

        self.org_ids: dict[str, str] = {}  # slug -> id
        self.user_ids: dict[str, str] = {}  # email -> id
        self.user_tokens: dict[str, str] = {}  # email -> access_token
        self.admin_token: str | None = None

    def check_api_health(self) -> bool:
        """Verify API is running."""
        try:
            # Try the OpenAPI endpoint which should always exist
            response = self.http.get(f"{self.api_url}/openapi.json")
            if response.status_code == 200:
                return True
            # Fallback: try docs
            response = self.http.get(f"{self.api_url}/docs")
            return response.status_code == 200
        except httpx.ConnectError:
            return False

    def check_environment(self) -> bool:
        """Safety checks before seeding."""
        url = os.getenv("SUPABASE_URL", "")

        if "supabase.co" in url and "local" not in url:
            env = os.getenv("ENVIRONMENT", "").lower()
            if env == "production":
                print("❌ ERROR: Cannot run seed in PRODUCTION!")
                return False

            print("⚠️  WARNING: Remote Supabase instance detected.")
            confirm = input("Type 'yes' to continue: ")
            if confirm.lower() != "yes":
                return False

        return True

    def clean_data(self) -> None:
        """Remove test data."""
        print("\n🧹 Cleaning existing data...")

        for user in DEV_USERS:
            try:
                profile = (
                    self.supabase.table("profiles")
                    .select("id")
                    .eq("email", user.email)
                    .execute()
                )
                if profile.data:
                    user_id = profile.data[0]["id"]
                    self.supabase.auth.admin.delete_user(user_id)
                    print(f"   🗑️  Deleted: {user.email}")
            except Exception as e:
                print(f"   ⚠️  Could not delete {user.email}: {e}")

        for org in DEV_ORGANIZATIONS:
            try:
                self.supabase.table("organizations").delete().eq(
                    "slug", org.slug
                ).execute()
                print(f"   🗑️  Deleted org: {org.slug}")
            except Exception:
                pass

        print("   ✅ Cleanup complete")

    def register_user(self, user: UserConfig) -> str | None:
        """Register user via API endpoint."""
        try:
            response = self.http.post(
                f"{self.api_url}/auth/register",
                json={
                    "email": user.email,
                    "password": user.password,
                    "full_name": user.full_name,
                },
            )

            if response.status_code == 201:
                data = response.json()
                user_id = data.get("user", {}).get("id")
                token = data.get("access_token")

                if user_id:
                    self.user_ids[user.email] = user_id
                if token:
                    self.user_tokens[user.email] = token

                print(f"   ✅ Registered: {user.email}")
                return user_id

            elif response.status_code == 202:
                # Email confirmation required - user created but no session
                print(f"   ⚠️  Registered (needs email confirm): {user.email}")
                # Get user ID from profiles
                profile = (
                    self.supabase.table("profiles")
                    .select("id")
                    .eq("email", user.email)
                    .execute()
                )
                if profile.data:
                    user_id = profile.data[0]["id"]
                    self.user_ids[user.email] = user_id
                    return user_id
                return None

            elif "already" in response.text.lower():
                print(f"   ℹ️  Already exists: {user.email}")
                return self._get_existing_user_id(user.email)

            else:
                print(f"   ❌ Failed ({response.status_code}): {user.email}")
                print(f"      {response.text[:200]}")
                return None

        except Exception as e:
            print(f"   ❌ Error: {user.email} - {e}")
            return None

    def _get_existing_user_id(self, email: str) -> str | None:
        """Get user ID from database if already exists."""
        try:
            profile = (
                self.supabase.table("profiles")
                .select("id")
                .eq("email", email)
                .execute()
            )
            if profile.data:
                user_id = profile.data[0]["id"]
                self.user_ids[email] = user_id
                return user_id
        except Exception:
            pass
        return None

    def login_user(self, email: str, password: str = DEFAULT_PASSWORD) -> str | None:
        """Login user via API and get token."""
        try:
            response = self.http.post(
                f"{self.api_url}/auth/login",
                json={"email": email, "password": password},
            )

            if response.status_code == 200:
                data = response.json()
                token = data.get("access_token")
                if token:
                    self.user_tokens[email] = token
                    print(f"   🔐 Logged in: {email}")
                    return token
            else:
                print(f"   ⚠️  Login failed for {email}: {response.status_code}")

        except Exception as e:
            print(f"   ⚠️  Login error for {email}: {e}")

        return None

    def set_platform_admin(self, user_id: str, email: str) -> None:
        """Promote user to platform admin (requires direct DB access)."""
        try:
            self.supabase.table("profiles").update({"is_platform_admin": True}).eq(
                "id", user_id
            ).execute()
            print("      🌟 Promoted to Platform Admin")

            # Log this action manually since it's a direct DB change
            self._log_audit_direct(
                actor_id=user_id,
                action="PROMOTE_PLATFORM_ADMIN",
                category="system",
                resource="profile",
                resource_id=user_id,
                metadata={"email": email, "source": "seed_script"},
            )
        except Exception as e:
            print(f"      ⚠️  Could not set admin: {e}")

    def create_organization(self, org: OrgConfig, admin_token: str) -> str | None:
        """Create organization via API (requires platform admin)."""
        try:
            response = self.http.post(
                f"{self.api_url}/organizations/",  # Trailing slash required
                json={
                    "name": org.name,
                    "slug": org.slug,
                    "type": org.org_type,
                    "settings": org.settings,
                },
                headers={"Authorization": f"Bearer {admin_token}"},
            )

            if response.status_code in [200, 201]:
                data = response.json()
                org_id = data.get("id")
                if org_id:
                    self.org_ids[org.slug] = org_id
                    print(f"   ✅ Created: {org.name}")
                    return org_id

            elif response.status_code == 409 or "already" in response.text.lower():
                print(f"   ℹ️  Already exists: {org.slug}")
                return self._get_existing_org_id(org.slug)

            else:
                print(f"   ❌ Failed ({response.status_code}): {org.name}")
                print(f"      {response.text[:200]}")
                # Fallback to direct creation
                return self._create_org_direct(org)

        except Exception as e:
            print(f"   ❌ Error creating {org.name}: {e}")
            return self._create_org_direct(org)

    def _create_org_direct(self, org: OrgConfig) -> str | None:
        """Fallback: create org directly in DB."""
        try:
            response = (
                self.supabase.table("organizations")
                .upsert(
                    {
                        "name": org.name,
                        "slug": org.slug,
                        "type": org.org_type,
                        "description": org.description,
                        "settings": org.settings,
                    },
                    on_conflict="slug",
                )
                .execute()
            )

            if response.data:
                org_id = response.data[0]["id"]
                self.org_ids[org.slug] = org_id
                print(f"   ✅ Created (direct): {org.name}")
                return org_id
        except Exception as e:
            print(f"   ❌ Direct creation failed: {e}")
        return None

    def _get_existing_org_id(self, slug: str) -> str | None:
        """Get org ID from database."""
        try:
            org = (
                self.supabase.table("organizations")
                .select("id")
                .eq("slug", slug)
                .execute()
            )
            if org.data:
                org_id = org.data[0]["id"]
                self.org_ids[slug] = org_id
                return org_id
        except Exception:
            pass
        return None

    def add_membership(
        self, user_id: str, org_slug: str, role: str, admin_token: str | None = None
    ) -> None:
        """Add user to organization with role."""
        org_id = self.org_ids.get(org_slug)
        if not org_id:
            org_id = self._get_existing_org_id(org_slug)

        if not org_id:
            print(f"      ⚠️  Org not found: {org_slug}")
            return

        # Try via API first if we have admin token
        if admin_token:
            try:
                response = self.http.post(
                    f"{self.api_url}/organizations/{org_id}/members",
                    json={"user_id": user_id, "role": role},
                    headers={"Authorization": f"Bearer {admin_token}"},
                )
                if response.status_code in [200, 201]:
                    print(f"      🔗 {org_slug} → {role} (via API)")
                    return
                elif response.status_code == 409:
                    print(f"      ℹ️  {org_slug} → {role} (ya existe)")
                    return
            except Exception:
                pass

        # Fallback to direct DB
        try:
            self.supabase.table("organization_members").upsert(
                {
                    "organization_id": org_id,
                    "user_id": user_id,
                    "role": role,
                    "status": "active",
                },
                on_conflict="organization_id,user_id",
            ).execute()
            print(f"      🔗 {org_slug} → {role}")

            # Log membership creation
            self._log_audit_direct(
                actor_id=user_id,
                action="JOIN_ORGANIZATION",
                category="org",
                organization_id=org_id,
                resource="membership",
                resource_id=user_id,
                metadata={"role": role, "source": "seed_script"},
            )
        except Exception as e:
            print(f"      ⚠️  Membership failed: {e}")

    def _log_audit_direct(
        self,
        actor_id: str,
        action: str,
        category: str,
        organization_id: str | None = None,
        resource: str | None = None,
        resource_id: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Insert audit log directly (for operations that bypass API)."""
        try:
            actor_email = None
            profile = (
                self.supabase.table("profiles")
                .select("email")
                .eq("id", actor_id)
                .execute()
            )
            if profile.data:
                actor_email = profile.data[0].get("email")

            self.supabase.schema("audit").from_("logs").insert(
                {
                    "actor_id": actor_id,
                    "actor_email": actor_email,
                    "organization_id": organization_id,
                    "category_code": category,
                    "action": action,
                    "resource": resource,
                    "resource_id": resource_id,
                    "metadata": metadata or {},
                    "ip_address": "127.0.0.1",
                    "user_agent": "OASIS-Seed-Script/1.0",
                }
            ).execute()
        except Exception:
            pass  # Silent fail for audit logs

    def seed_all(self) -> None:
        """Run full seed process."""
        print("\n" + "=" * 60)
        print("👥 PHASE 1: Register Users via API")
        print("=" * 60)

        # Register all users via API (generates REGISTER logs)
        for user in DEV_USERS:
            user_id = self.register_user(user)

            if user_id and user.is_platform_admin:
                self.set_platform_admin(user_id, user.email)

        print("\n" + "=" * 60)
        print("🔐 PHASE 2: Login Users via API")
        print("=" * 60)

        # Login all users (generates LOGIN logs)
        for user in DEV_USERS:
            token = self.login_user(user.email, user.password)
            if user.is_platform_admin and token:
                self.admin_token = token

        print("\n" + "=" * 60)
        print("🏢 PHASE 3: Create Organizations")
        print("=" * 60)

        # Create organizations (requires platform admin)
        if self.admin_token:
            for org in DEV_ORGANIZATIONS:
                self.create_organization(org, self.admin_token)
        else:
            print("   ⚠️  No admin token, creating orgs directly")
            for org in DEV_ORGANIZATIONS:
                self._create_org_direct(org)

        print("\n" + "=" * 60)
        print("🔗 PHASE 4: Assign Memberships")
        print("=" * 60)

        # Assign memberships
        for user in DEV_USERS:
            user_id = self.user_ids.get(user.email)
            if not user_id:
                continue

            print(f"   {user.email}:")
            for org_slug, role in user.memberships:
                self.add_membership(user_id, org_slug, role, self.admin_token)

    def print_summary(self) -> None:
        """Print seed summary."""
        print("\n" + "=" * 60)
        print("📋 SEED COMPLETE")
        print("=" * 60)

        print("\n🏢 Organizations:")
        for slug, org_id in self.org_ids.items():
            print(f"   • {slug}: {org_id[:8]}...")

        print(f"\n👥 Users (password: {DEFAULT_PASSWORD}):")
        print("-" * 60)

        for user in DEV_USERS:
            user_id = self.user_ids.get(user.email, "???")
            roles = []
            if user.is_platform_admin:
                roles.append("🌟 Platform Admin")
            for org_slug, role in user.memberships:
                roles.append(f"{org_slug}:{role}")

            role_str = ", ".join(roles) if roles else "Community only"
            print(f"   {user.email}")
            print(f"      ID: {user_id[:8] if user_id != '???' else '???'}...")
            print(f"      Roles: {role_str}")

        print("-" * 60)
        print("\n✅ Check audit.logs table - you should see REGISTER and LOGIN events!")
        print(f"\n   API: {self.api_url}")


# =============================================================================
# MAIN
# =============================================================================


def main():
    parser = argparse.ArgumentParser(description="Seed OASIS development data via API")
    parser.add_argument(
        "--clean", action="store_true", help="Clean existing data first"
    )
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="API base URL")
    args = parser.parse_args()

    load_dotenv()

    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not service_role_key:
        print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env")
        sys.exit(1)

    print("🚀 OASIS Development Seeder (API Mode)")
    print(f"   API: {args.api_url}")
    print(f"   Supabase: {supabase_url}")

    seeder = DevSeeder(args.api_url, supabase_url, service_role_key)

    # Check API is running
    if not seeder.check_api_health():
        print("\n❌ API is not running!")
        print("   Start it with: uvicorn services.auth_service.main:app --reload")
        print("   Then run this script again.")
        sys.exit(1)

    print("   ✅ API is healthy")

    if not seeder.check_environment():
        sys.exit(1)

    if args.clean:
        seeder.clean_data()

    seeder.seed_all()
    seeder.print_summary()


if __name__ == "__main__":
    main()
