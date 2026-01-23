import asyncio
import os
import sys

from dotenv import load_dotenv

from supabase import Client, create_client

# Cargar variables de entorno
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    print("Error: Faltan SUPABASE_URL o SUPABASE_SERVICE_KEY en el archivo .env")
    sys.exit(1)

# Cliente con privilegios de administrador
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


async def main():
    print("🚀 Iniciando Seed de Datos Multi-Tenant...")

    # ==========================================
    # 1. Definir Estructura de Organizaciones
    # ==========================================
    orgs_data = [
        {
            "name": "Fundación Summer",
            "slug": "fundacion-summer",
            "type": "provider",
            "settings": {"theme": "summer", "features": ["admin_panel", "analytics"]},
        },
        {
            "name": "Banco Demo B2B",
            "slug": "banco-demo",
            "type": "sponsor",
            "settings": {"theme": "corporate_blue", "features": ["reports"]},
        },
        # Nota: "Oasis Community" se crea en la migración SQL, no es necesario aquí,
        # pero podríamos buscarla para asignarla si quisiéramos.
    ]

    created_orgs = {}

    print("\n🏢 Creando/Sincronizando Organizaciones...")
    for org in orgs_data:
        # Upsert: Inserta o actualiza si existe el slug
        response = (
            supabase.table("organizations").upsert(org, on_conflict="slug").execute()
        )

        if response.data:
            org_id = response.data[0]["id"]
            created_orgs[org["slug"]] = org_id
            print(f"   ✅ Org '{org['name']}' lista (ID: {org_id})")
        else:
            print(f"   ❌ Error creando org {org['name']}")

    # ==========================================
    # 2. Definir Usuarios y sus Roles
    # ==========================================
    users_data = [
        {
            "email": "admin@oasis.com",
            "password": "password123",
            "full_name": "Super Admin Oasis",
            "is_platform_admin": True,
            "memberships": [{"org_slug": "fundacion-summer", "role": "owner"}],
        },
        {
            "email": "gestor@summer.com",
            "password": "password123",
            "full_name": "Gestor Summer",
            "is_platform_admin": False,
            "memberships": [{"org_slug": "fundacion-summer", "role": "admin"}],
        },
        {
            "email": "empleado@banco.com",
            "password": "password123",
            "full_name": "Juan Empleado",
            "is_platform_admin": False,
            "memberships": [{"org_slug": "banco-demo", "role": "participante"}],
        },
        {
            "email": "facilitador@banco.com",
            "password": "password123",
            "full_name": "Laura Facilitadora",
            "is_platform_admin": False,
            "memberships": [
                {"org_slug": "banco-demo", "role": "facilitador"},
                # Laura también colabora con la fundación
                {"org_slug": "fundacion-summer", "role": "participante"},
            ],
        },
        {
            "email": "visitante@gmail.com",
            "password": "password123",
            "full_name": "Pepe Visitante",
            "is_platform_admin": False,
            "memberships": [],  # Sin membresía explícita -> caerá en "Oasis Community" por el trigger
        },
    ]

    print("\nbusts👥 Creando Usuarios y Asignando Membresías...")

    for user in users_data:
        try:
            # A. Crear Usuario en Auth (o recuperar si existe)
            # Intentamos crear. Si falla, asumimos que existe y buscamos su ID.
            # Nota: admin.create_user auto-confirma el email.
            user_id = None

            try:
                auth_response = supabase.auth.admin.create_user(
                    {
                        "email": user["email"],
                        "password": user["password"],
                        "email_confirm": True,
                        "user_metadata": {"full_name": user["full_name"]},
                    }
                )
                user_id = auth_response.user.id
                print(f"   👤 Usuario creado: {user['email']}")
            except Exception as e:
                # Si el usuario ya existe, necesitamos buscar su ID en la tabla profiles
                # porque la API de admin.create_user lanza error.
                existing_user = (
                    supabase.table("profiles")
                    .select("id")
                    .eq("email", user["email"])
                    .execute()
                )
                if existing_user.data:
                    user_id = existing_user.data[0]["id"]
                    print(f"   ℹ️  Usuario ya existía: {user['email']}")
                else:
                    print(f"   ❌ Error crítico con usuario {user['email']}: {e}")
                    continue

            if user["is_platform_admin"]:
                (
                    supabase.table("profiles")
                    .update({"is_platform_admin": True})
                    .eq("id", user_id)
                    .execute()
                )
                print("      🌟 Set Platform Admin: TRUE")

            if user["memberships"]:
                for m in user["memberships"]:
                    slug = m["org_slug"]
                    role = m["role"]

                    if slug in created_orgs:
                        org_id = created_orgs[slug]

                        membership_data = {
                            "organization_id": org_id,
                            "user_id": user_id,
                            "role": role,
                            "status": "active",
                        }

                        # Upsert en la tabla de miembros
                        m_res = (
                            supabase.table("organization_members")
                            .upsert(
                                membership_data,
                                on_conflict="organization_id,user_id",
                            )
                            .execute()
                        )

                        if m_res.data:
                            print(f"      🔗 Vinculado a '{slug}' como '{role}'")
                    else:
                        print(f"      ⚠️  Org '{slug}' no encontrada para vincular.")
            else:
                print("      🌱 Sin membresías B2B (Usuario Comunidad)")

        except Exception as e:
            print(f"   ❌ Error procesando {user['email']}: {str(e)}")

    print("\n✅ Seed completado exitosamente.")


if __name__ == "__main__":
    asyncio.run(main())
