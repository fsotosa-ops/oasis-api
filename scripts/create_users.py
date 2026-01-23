import asyncio
import os
import sys

# Ajuste de path para que encuentre el módulo 'common'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.config import settings
from supabase import create_async_client


async def seed_users():
    print(f"🚀 Iniciando sembrado de usuarios en: {settings.SUPABASE_URL}")

    # Usamos la SERVICE_ROLE_KEY para tener privilegios de admin
    supabase = await create_async_client(
        settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY
    )

    # Lista de usuarios de prueba para la Matriz de Roles
    test_users = [
        {
            "email": "owner@oasis.com",
            "password": "password123",
            "role": "owner",
            "name": "Gran Arquitecto",
        },
        {
            "email": "admin@oasis.com",
            "password": "password123",
            "role": "admin",
            "name": "Admin Sistema",
        },
        {
            "email": "gestor@oasis.com",
            "password": "password123",
            "role": "gestor",
            "name": "Colaborador Eventos",
        },
        {
            "email": "participante@oasis.com",
            "password": "password123",
            "role": "participante",
            "name": "Jugador Uno",
        },
        {
            "email": "visitante@oasis.com",
            "password": "password123",
            "role": "visitante",
            "name": "Visitante Curioso",
        },
    ]

    for user_data in test_users:
        try:
            print(f"👤 Creando: {user_data['email']} ({user_data['role']})...")

            # 1. Crear usuario en Auth (GoTrue)
            auth_response = await supabase.auth.admin.create_user(
                {
                    "email": user_data["email"],
                    "password": user_data["password"],
                    "email_confirm": True,  # Auto-confirmar email
                    "user_metadata": {"full_name": user_data["name"]},
                }
            )

            if auth_response.user:
                user_id = auth_response.user.id

                # 2. Actualizar el rol en la tabla public.profiles
                await supabase.table("profiles").update({"role": user_data["role"]}).eq(
                    "id", user_id
                ).execute()

                print(f"   ✅ Usuario creado y rol actualizado a {user_data['role']}")

        except Exception as e:
            # Si el usuario ya existe, suele lanzar excepción, lo manejamos suavemente
            if "User already registered" in str(e):
                print(f"   ⚠️  El usuario {user_data['email']} ya existe.")
            else:
                print(f"   ❌ Error creando {user_data['email']}: {e}")

    print("\n✨ Sembrado finalizado exitosamente.")


if __name__ == "__main__":
    asyncio.run(seed_users())
