-- =============================================================================
-- SEED: Production Data
-- =============================================================================
-- This file contains ONLY essential data required for the application to work.
-- NO test users or demo data - those go in scripts/seed_dev.py
--
-- Run with: supabase db reset (includes migrations + seed)
-- =============================================================================

-- Ensure community organization exists
-- (The migration creates it, but this ensures idempotency)
-- UUID is auto-generated, referenced by slug
INSERT INTO public.organizations (name, slug, type, description, settings)
VALUES (
    'OASIS Community',
    'oasis-community',
    'community',
    'Comunidad abierta de OASIS. Todos los usuarios son miembros por defecto.',
    '{"is_default": true, "features": ["public_content"]}'::jsonb
)
ON CONFLICT (slug) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    settings = EXCLUDED.settings;

-- Ensure audit categories exist
INSERT INTO audit.categories (code, label, description) VALUES
    ('auth', 'Seguridad', 'Logins, registro, logout'),
    ('org', 'Organización', 'Cambios en empresa, miembros e invitaciones'),
    ('billing', 'Facturación', 'Pagos y suscripciones'),
    ('journey', 'Experiencia', 'Avance de usuarios en journeys'),
    ('system', 'Sistema', 'Errores y tareas automáticas'),
    ('user', 'Usuario', 'Cambios en perfil y preferencias')
ON CONFLICT (code) DO NOTHING;

-- =============================================================================
-- NOTE: First platform admin should be created via:
--   1. Register normally through the API
--   2. Run: UPDATE profiles SET is_platform_admin = true WHERE email = 'your@email.com';
-- =============================================================================
