from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# 1. Imports de Common (Rutas Absolutas como en tus archivos)
from common.auth.security import get_current_user
from common.database.client import get_admin_client, get_supabase_client

# 2. Imports de Schemas (Asumiendo que creaste el archivo organizations.py en schemas)
from services.auth_service.schemas.organizations import (
    MemberAdd,
    MembershipOut,
    OrganizationCreate,
    OrganizationOut,
)

router = APIRouter()
security = HTTPBearer()
# --- ENDPOINTS ---


@router.post("/", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
async def create_organization(
    org_in: OrganizationCreate,
    current_user: dict = Depends(get_current_user),  # noqa: B008
    # Usamos admin_db para escribir saltándonos las reglas RLS
    admin_db=Depends(get_admin_client),  # noqa: B008
):
    user_id = current_user["id"]

    # 1. Crear Organización (Usando permisos de Super Admin)
    try:
        org_res = (
            await admin_db.table("organizations")
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
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail="Error creando organización. ¿Quizás el slug ya existe?",
        ) from e

    new_org = org_res.data[0]

    # 2. Asignar Owner (Usando permisos de Super Admin)
    # Esto es seguro porque lo hace el Backend, no el usuario.
    member_data = {
        "organization_id": new_org["id"],
        "user_id": user_id,
        "role": "owner",
        "status": "active",
    }

    await admin_db.table("organization_members").insert(member_data).execute()

    return new_org


@router.get("/mine", response_model=list[OrganizationOut])
async def get_my_organizations(
    current_user: dict = Depends(get_current_user),  # noqa: B008
    db=Depends(get_supabase_client),  # noqa: B008
    token: HTTPAuthorizationCredentials = Depends(security),  # noqa: B008
):

    user_id = current_user["id"]
    db.postgrest.auth(token.credentials)

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
    token: HTTPAuthorizationCredentials = Depends(security),  # noqa: B008
    admin_db=Depends(get_admin_client),  # noqa: B008
):
    # 1. Autenticar contexto del solicitante
    db.postgrest.auth(token.credentials)
    requester_id = current_user["id"]

    # 2. Verificar Permisos (Usamos 'db' con RLS)
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

    # 3. Buscar usuario destino (Usando ADMIN_DB)
    # Soporta búsqueda por email O por user_id
    target_user_id = None

    if member_in.user_id:
        # --- ESCENARIO A: Búsqueda por user_id ---
        target_user_res = (
            await admin_db.table("profiles")
            .select("id")
            .eq("id", member_in.user_id)
            .limit(1)
            .execute()
        )
        if target_user_res.data:
            target_user_id = target_user_res.data[0]["id"]
        else:
            raise HTTPException(
                status_code=404,
                detail="Usuario no encontrado con el ID proporcionado.",
            )

    elif member_in.email:
        # --- ESCENARIO B: Búsqueda por email ---
        target_user_res = (
            await admin_db.table("profiles")
            .select("id")
            .eq("email", member_in.email)
            .limit(1)
            .execute()
        )

        if target_user_res.data:
            # Usuario existe - obtener su ID
            target_user_id = target_user_res.data[0]["id"]
        else:
            # Usuario NO existe - TODO: Implementar invitaciones pendientes
            # Por ahora retornamos error indicando que se podría invitar
            raise HTTPException(
                status_code=404,
                detail=(
                    "Usuario no registrado en la plataforma."
                    "(Invitaciones pendientes por implementar)"
                ),
            )

    # Verificar si ya es miembro
    # Usamos count='exact', head=True para verificar existencia eficientemente
    existing_member = (
        await admin_db.table("organization_members")
        .select("id", count="exact", head=True)
        .eq("organization_id", org_id)
        .eq("user_id", target_user_id)
        .execute()
    )

    if existing_member.count > 0:
        raise HTTPException(
            status_code=409, detail="El usuario ya pertenece a esta organización"
        )

    # Insertar Membresía (Usando ADMIN_DB)
    new_member_data = {
        "organization_id": org_id,
        "user_id": target_user_id,
        "role": member_in.role,
        "status": "active",
    }

    try:
        res = (
            await admin_db.table("organization_members")
            .insert(new_member_data)
            .execute()
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail="Error al agregar miembro") from e

    # 5. Retornar respuesta completa
    query = (
        "role, status, joined_at, "
        "organizations(id, name, slug, type, settings, created_at)"
    )

    full_member = (
        await admin_db.table("organization_members")
        .select(query)
        .eq("id", res.data[0]["id"])
        .single()
        .execute()
    )

    org_data = full_member.data.get("organizations")
    if not org_data:
        raise HTTPException(
            status_code=500, detail="Error de integridad: Organización no encontrada"
        )

    return {
        "role": full_member.data["role"],
        "status": full_member.data["status"],
        "joined_at": full_member.data["joined_at"],
        "organization": org_data,
    }


@router.patch("/{org_id}/members/{user_id}", response_model=MembershipOut)
async def update_member_role(
    org_id: str,
    user_id: str,
    member_in: MemberAdd,  # Reutilizamos para el campo 'role'
    current_user: dict = Depends(get_current_user),  # noqa: B008
    db=Depends(get_supabase_client),  # noqa: B008
    token: HTTPAuthorizationCredentials = Depends(security),  # noqa: B008
    admin_db=Depends(get_admin_client),  # noqa: B008
):
    """Actualiza el rol de un usuario dentro de una organización específica."""
    db.postgrest.auth(token.credentials)
    requester_id = current_user["id"]

    # 1. Verificar que el que pide sea Owner/Admin de esa Org
    perms = (
        await db.table("organization_members")
        .select("role")
        .eq("organization_id", org_id)
        .eq("user_id", requester_id)
        .single()
        .execute()
    )

    if not perms.data or perms.data["role"] not in ["owner", "admin"]:
        raise HTTPException(status_code=403, detail="No tienes permisos suficientes")

    # 2. Actualizar el rol (Usando admin_db por RLS)
    update_res = (
        await admin_db.table("organization_members")
        .update({"role": member_in.role})
        .eq("organization_id", org_id)
        .eq("user_id", user_id)
        .execute()
    )

    if not update_res.data:
        raise HTTPException(status_code=404, detail="Membresía no encontrada")

    # 3. Retornar objeto completo
    query = (
        "role, status, joined_at, "
        "organizations(id, name, slug, type, settings, created_at)"
    )
    full_member = (
        await admin_db.table("organization_members")
        .select(query)
        .eq("id", update_res.data[0]["id"])
        .single()
        .execute()
    )

    return {
        "role": full_member.data["role"],
        "status": full_member.data["status"],
        "joined_at": full_member.data["joined_at"],
        "organization": full_member.data["organizations"],
    }
