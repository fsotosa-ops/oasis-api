-- 1. Tabla Maestra de Categorías de Eventos
CREATE TABLE public.log_categories (
    code TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    description TEXT,
    retention_days INT DEFAULT 365
);

-- Seguridad para Categorías (Lectura pública, Escritura restringida)
ALTER TABLE public.log_categories ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read access" ON public.log_categories FOR SELECT USING (true);

-- Seed inicial de configuración
INSERT INTO public.log_categories (code, label, description) VALUES
    ('auth', 'Seguridad', 'Logins, cambios de password, 2FA'),
    ('profile', 'Perfil de Usuario', 'Cambios de rol, actualización de datos personales'),
    ('billing', 'Facturación', 'Pagos, cambios de suscripción, facturas'),
    ('system', 'Sistema', 'Errores internos, tareas programadas'),
    ('compliance', 'Legal', 'Aceptación de términos, descargas de datos GDPR');

-- 2. Tabla de Logs (Audit Trail)
CREATE TABLE public.profile_logs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
    category_code TEXT REFERENCES public.log_categories(code) NOT NULL,
    action_code TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_logs_user ON public.profile_logs(user_id);
CREATE INDEX idx_logs_category ON public.profile_logs(category_code);
CREATE INDEX idx_logs_meta ON public.profile_logs USING gin (metadata);

-- ---------------------------------------------------------
-- 3. Habilitar Seguridad (RLS) en Logs
-- ---------------------------------------------------------
ALTER TABLE public.profile_logs ENABLE ROW LEVEL SECURITY;

-- Política: Solo Admins y Owners pueden ver los logs
CREATE POLICY "Admins can view logs"
ON public.profile_logs FOR SELECT
USING (
  EXISTS (
    SELECT 1 FROM public.profiles
    WHERE id = auth.uid() AND role IN ('owner', 'admin')
  )
);

-- (Opcional) Política: Nadie puede borrar ni insertar manualmente vía API pública
-- Los inserts se hacen vía Trigger (postgres) o Service Key (backend)

-- 4. Trigger Automático
CREATE OR REPLACE FUNCTION public.handle_profile_log()
RETURNS TRIGGER AS $$
BEGIN
  IF OLD.role IS DISTINCT FROM NEW.role THEN
    INSERT INTO public.profile_logs (
        user_id,
        category_code,
        action_code,
        metadata
    )
    VALUES (
        NEW.id,
        'profile',
        CASE
            WHEN NEW.role = 'owner' THEN 'PROMOTE_TO_OWNER'
            ELSE 'ROLE_CHANGE'
        END,
        jsonb_build_object(
            'previous_role', OLD.role,
            'new_role', NEW.role,
            'triggered_by', 'system_trigger'
        )
    );
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_profile_update_log
  AFTER UPDATE ON public.profiles
  FOR EACH ROW
  EXECUTE PROCEDURE public.handle_profile_log();
