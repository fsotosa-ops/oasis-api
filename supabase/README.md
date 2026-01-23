# Supabase Database Setup

## Estructura de Archivos

```
supabase/
├── migrations/
│   ├── 20260122000001_init_schema.sql    # Tablas, ENUMs, triggers
│   ├── 20260122000002_rls_policies.sql   # Row Level Security
│   └── 20260122000003_audit_system.sql   # Sistema de auditoría
├── seed.sql                               # Datos mínimos para producción
└── README.md                              # Este archivo
```

## Comandos Supabase CLI

### Setup Inicial (Primera vez)

```bash
# 1. Instalar Supabase CLI (si no lo tienes)
brew install supabase/tap/supabase

# 2. Login a Supabase
supabase login

# 3. Inicializar proyecto (si es nuevo)
supabase init

# 4. Linkear con proyecto remoto
supabase link --project-ref <tu-project-ref>
```

### Desarrollo Local

```bash
# Iniciar Supabase local (Docker requerido)
supabase start

# Ver status
supabase status

# Detener
supabase stop
```

### Migraciones

```bash
# Crear nueva migración
supabase migration new nombre_descriptivo

# Aplicar migraciones pendientes (local)
supabase db push

# Reset completo (DROP ALL + migrations + seed)
supabase db reset

# Ver migraciones aplicadas
supabase migration list

# Ver diferencias entre local y remoto
supabase db diff
```

### Seed de Datos

```bash
# Producción: Solo seed.sql (ejecutado con db reset)
supabase db reset

# Desarrollo: Usar script Python
python scripts/seed_dev.py

# Desarrollo: Limpiar y re-seedear
python scripts/seed_dev.py --clean

# Solo organizaciones
python scripts/seed_dev.py --orgs-only

# Solo usuarios
python scripts/seed_dev.py --users-only
```

### Deploy a Producción

```bash
# Ver cambios pendientes
supabase db diff --linked

# Aplicar migraciones a producción
supabase db push --linked

# ⚠️ CUIDADO: Reset en producción (BORRA TODO)
# supabase db reset --linked
```

## Flujos de Trabajo

### 1. Nuevo Desarrollador

```bash
# Clonar repo
git clone <repo>
cd oasis-api

# Configurar Supabase local
supabase start
supabase db reset

# Crear datos de prueba
python scripts/seed_dev.py

# Iniciar API
uvicorn services.auth_service.main:app --reload
```

### 2. Agregar Nueva Tabla/Cambio de Schema

```bash
# 1. Crear migración
supabase migration new add_payments_table

# 2. Editar el archivo generado en migrations/
# 3. Aplicar localmente
supabase db push

# 4. Probar
# 5. Commit y PR
git add supabase/migrations/
git commit -m "feat(db): add payments table"

# 6. Después del merge, aplicar en staging/prod
supabase db push --linked
```

### 3. Debugging de RLS

```bash
# Conectar a la DB local
psql postgresql://postgres:postgres@localhost:54322/postgres

# Ver políticas activas
SELECT * FROM pg_policies WHERE tablename = 'profiles';

# Probar como usuario específico
SET request.jwt.claims = '{"sub": "user-uuid-here"}';
SELECT * FROM profiles;  -- Verás solo lo permitido por RLS
```

## Usuarios de Prueba (seed_dev.py)

| Email | Rol | Password |
|-------|-----|----------|
| admin@oasis.dev | Platform Admin + Owner | Test123! |
| owner@summer.dev | Org Owner | Test123! |
| admin@summer.dev | Org Admin | Test123! |
| facilitador@summer.dev | Facilitador (multi-org) | Test123! |
| participante1@banco.dev | Participante | Test123! |
| multi@oasis.dev | Multiple roles | Test123! |
| visitante@gmail.dev | Solo Community | Test123! |

## Troubleshooting

### Error: "relation does not exist"
```bash
# Las migraciones no se aplicaron
supabase db reset
```

### Error: "permission denied for schema"
```bash
# Verificar grants en la migración
# Revisar que service_role tenga acceso
```

### Error: "RLS policy violation"
```bash
# El usuario no tiene permiso
# Revisar políticas en 20260122000002_rls_policies.sql
# Verificar que el JWT tenga el claim correcto
```

### Resetear Supabase local completamente
```bash
supabase stop
supabase start
supabase db reset
python scripts/seed_dev.py
```
