DROP SCHEMA IF EXISTS audit CASCADE;

-- ==============================================================================
-- 1. ESQUEMA & SEGURIDAD BASE
-- ==============================================================================
-- Creamos un esquema separado para no ensuciar 'public' y aislar permisos
CREATE SCHEMA IF NOT EXISTS audit;

-- 1. Asegurar acceso al esquema
GRANT USAGE ON SCHEMA audit TO service_role;
GRANT USAGE ON SCHEMA audit TO postgres;
GRANT USAGE ON SCHEMA audit TO anon;
GRANT USAGE ON SCHEMA audit TO authenticated;

-- 2. Dar permisos TOTALES al service_role (Tu backend) en tablas ACTUALES
GRANT ALL ON ALL TABLES IN SCHEMA audit TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA audit TO service_role;

-- 3. IMPORTANTE: Configurar permisos AUTOMÁTICOS para tablas FUTURAS
-- Esto evita que el error vuelva si haces un DROP/CREATE table mañana
ALTER DEFAULT PRIVILEGES IN SCHEMA audit GRANT ALL ON TABLES TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA audit GRANT ALL ON SEQUENCES TO service_role;

-- 4. Permisos de LECTURA para usuarios autenticados (opcional, para dashboard)
GRANT SELECT ON ALL TABLES IN SCHEMA audit TO authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA audit GRANT SELECT ON TABLES TO authenticated;

-- 5. Bloquear escritura a usuarios normales (Seguridad)
REVOKE INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA audit FROM authenticated;
REVOKE INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA audit FROM anon;

-- ==============================================================================
-- 2. TABLAS
-- ==============================================================================
-- Tabla de Categorías (Maestra)
CREATE TABLE IF NOT EXISTS audit.categories (
    code TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    description TEXT,
    retention_days INT DEFAULT 365,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed de Categorías
INSERT INTO audit.categories (code, label, description) VALUES
    ('auth', 'Seguridad', 'Logins, registro, logout'),
    ('org', 'Organización', 'Cambios en empresa, miembros e invitaciones'),
    ('billing', 'Facturación', 'Pagos y suscripciones'),
    ('journey', 'Experiencia', 'Avance de usuarios en journeys'),
    ('system', 'Sistema', 'Errores y tareas automáticas')
ON CONFLICT (code) DO NOTHING;

-- Tabla de Logs (El historial)
CREATE TABLE IF NOT EXISTS audit.logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    occurred_at TIMESTAMPTZ DEFAULT NOW(),

    -- Quién y Dónde
    organization_id UUID REFERENCES public.organizations(id) ON DELETE SET NULL,
    actor_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    actor_email TEXT, -- Snapshot del email por si el usuario se borra

    -- Qué
    category_code TEXT REFERENCES audit.categories(code),
    action TEXT NOT NULL,

    -- Detalles
    resource TEXT,
    resource_id UUID,
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Contexto Técnico
    ip_address INET,
    user_agent TEXT
);

-- Índices para búsqueda rápida
CREATE INDEX IF NOT EXISTS idx_audit_org ON audit.logs(organization_id);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit.logs(actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_date ON audit.logs(occurred_at DESC);

-- ==============================================================================
-- 3. ROW LEVEL SECURITY (RLS) - "Quién puede ver qué"
-- ==============================================================================
ALTER TABLE audit.categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit.logs ENABLE ROW LEVEL SECURITY;

-- POLÍTICA 1: Categorías son públicas para leer (necesario para filtros en Frontend)
CREATE POLICY "Public read categories" ON audit.categories FOR SELECT USING (true);

-- POLÍTICA 2: Platform Admins ven TODO
CREATE POLICY "Platform Admins view all logs"
ON audit.logs FOR SELECT
USING (
  EXISTS (
    SELECT 1 FROM public.profiles
    WHERE id = auth.uid() AND is_platform_admin = true
  )
);

-- POLÍTICA 3: Dueños de Organización ven logs de SU empresa
CREATE POLICY "Org Owners view org logs"
ON audit.logs FOR SELECT
USING (
  organization_id IN (
    SELECT organization_id FROM public.organization_members
    WHERE user_id = auth.uid() AND role IN ('owner', 'admin') AND status = 'active'
  )
);

-- POLÍTICA 4: Usuarios ven sus PROPIOS logs (historial personal)
CREATE POLICY "Users view own logs"
ON audit.logs FOR SELECT
USING (
  actor_id = auth.uid()
);

-- ==============================================================================
-- 4. HARDENING (Inmutabilidad) - Opcional pero recomendado
-- ==============================================================================
-- Trigger para evitar que alguien edite un log histórico (incluso por error)
CREATE OR REPLACE FUNCTION audit.prevent_log_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit logs are immutable. Cannot update or delete.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER check_audit_immutable
BEFORE UPDATE OR DELETE ON audit.logs
FOR EACH ROW
EXECUTE FUNCTION audit.prevent_log_modification();
