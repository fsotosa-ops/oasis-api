from fastapi import APIRouter, Depends, HTTPException, status

# 1. Imports de Common (Rutas Absolutas como en tus archivos)
from common.auth.security import get_current_user
from common.database.client import get_supabase_client

# 2. Imports de Schemas (Asumiendo que creaste el archivo organizations.py en schemas)
from services.auth_service.schemas.organizations import (
    MemberAdd,
    MembershipOut,
    OrganizationCreate,
    OrganizationOut,
)

router = APIRouter()

# --- ENDPOINTS ---


@router.post("/", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
async def create_organization(
    org_in: OrganizationCreate,
    current_user: dict = Depends(get_current_user),  # noqa: B008
    db=Depends(get_supabase_client),  # noqa: B008
):
    user_id = current_user["id"]

    # 1. Crear Organización
    # Nota: Manejar excepciones de duplicidad de slug aquí si es necesario
    org_res = (
        await db.table("organizations")
        .insert(
            {
                "name": org_in.name,
                "slug": org_in.slug,
                "type": org_in.type,
                "settings": org_in.settings,
            }
        )
        .execute()
    )

    if not org_res.data:
        raise HTTPException(status_code=400, detail="Error al crear organización")

    new_org = org_res.data[0]

    # 2. Asignar Owner (El usuario que crea es el dueño)
    member_data = {
        "organization_id": new_org["id"],
        "user_id": user_id,
        "role": "owner",
        "status": "active",
    }
    await db.table("organization_members").insert(member_data).execute()

    return new_org


@router.get("/mine", response_model=list[OrganizationOut])
async def get_my_organizations(
    current_user: dict = Depends(get_current_user),  # noqa: B008
    db=Depends(get_supabase_client),  # noqa: B008
):
    user_id = current_user["id"]

    # Traer organizaciones donde soy miembro activo
    res = (
        await db.table("organization_members")
        .select("organizations(*)")
        .eq("user_id", user_id)
        .eq("status", "active")
        .execute()
    )

    # Extraer el objeto anidado
    orgs = [item["organizations"] for item in res.data if item.get("organizations")]
    return orgs


@router.post("/{org_id}/members", response_model=MembershipOut)
async def add_member_to_org(
    org_id: str,
    member_in: MemberAdd,
    current_user: dict = Depends(get_current_user),  # noqa: B008
    db=Depends(get_supabase_client),  # noqa: B008
):
    requester_id = current_user["id"]

    # 1. Verificar Permisos (Solo Owner o Admin de esa org pueden invitar)
    perms = (
        await db.table("organization_members")
        .select("role")
        .eq("organization_id", org_id)
        .eq("user_id", requester_id)
        .single()
        .execute()
    )

    if not perms.data or perms.data["role"] not in ["owner", "admin"]:
        raise HTTPException(
            status_code=403, detail="No tienes permisos para invitar miembros"
        )

    # 2. Buscar ID del usuario por Email
    target_user = (
        await db.table("profiles")
        .select("id")
        .eq("email", member_in.email)
        .single()
        .execute()
    )

    if not target_user.data:
        raise HTTPException(
            status_code=404, detail="El usuario no está registrado en la plataforma"
        )

    target_user_id = target_user.data["id"]

    # 3. Insertar Membresía
    new_member_data = {
        "organization_id": org_id,
        "user_id": target_user_id,
        "role": member_in.role,
        "status": "active",
    }

    try:
        res = await db.table("organization_members").insert(new_member_data).execute()
    except Exception as e:
        raise HTTPException(
            status_code=400, detail="El usuario ya pertenece a esta organización"
        ) from e

    # 4. Retornar respuesta completa
    # Hacemos fetch para traer la org anidada y cumplir con el schema MembershipOut
    full_member = (
        await db.table("organization_members")
        .select("*, organizations(*)")
        .eq("id", res.data[0]["id"])
        .single()
        .execute()
    )

    # Mapeo manual si es necesario para ajustar al schema Pydantic
    return {
        "role": full_member.data["role"],
        "status": full_member.data["status"],
        "joined_at": full_member.data["joined_at"],
        "organization": full_member.data["organizations"],
    }
