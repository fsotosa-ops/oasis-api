-- supabase/migrations/20260122164512_init_auth_profiles.sql

-- 1. Habilitar extensiones
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 2. Limpieza de tipos (para evitar conflictos en re-runs)
DROP TYPE IF EXISTS public.user_role CASCADE;
DROP TYPE IF EXISTS public.org_type CASCADE;
DROP TYPE IF EXISTS public.member_role CASCADE;
DROP TYPE IF EXISTS public.member_status CASCADE;

-- 3. Definición de Enums
CREATE TYPE public.org_type AS ENUM ('sponsor', 'provider', 'community');
CREATE TYPE public.member_role AS ENUM ('owner', 'admin', 'facilitador', 'participante');
CREATE TYPE public.member_status AS ENUM ('active', 'invited', 'suspended');

-- 4. Tablas
CREATE TABLE IF NOT EXISTS public.organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    type public.org_type NOT NULL DEFAULT 'sponsor',
    settings JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID REFERENCES auth.users ON DELETE CASCADE NOT NULL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    is_platform_admin BOOLEAN DEFAULT false,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.organization_members (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES public.organizations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    role public.member_role NOT NULL DEFAULT 'participante',
    status public.member_status DEFAULT 'active',
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(organization_id, user_id)
);

-- 5. Habilitar RLS
ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organization_members ENABLE ROW LEVEL SECURITY;

-- 6. Funciones de Seguridad (SECURITY DEFINER)
-- Estas funciones permiten leer permisos sin causar recursión infinita

CREATE OR REPLACE FUNCTION public.get_is_platform_admin()
RETURNS BOOLEAN LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
  SELECT COALESCE((SELECT is_platform_admin FROM public.profiles WHERE id = auth.uid()), false);
$$;

CREATE OR REPLACE FUNCTION public.get_my_org_ids()
RETURNS SETOF UUID LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
  SELECT organization_id FROM public.organization_members WHERE user_id = auth.uid();
$$;

-- 7. Políticas RLS (Limpiamos previas para evitar error 42710)

-- === ORGANIZATIONS ===
DROP POLICY IF EXISTS "Users view own orgs" ON public.organizations;
CREATE POLICY "Users view own orgs" ON public.organizations FOR SELECT USING (
    id IN (SELECT public.get_my_org_ids()) OR type = 'community'
);

DROP POLICY IF EXISTS "Owners update org" ON public.organizations;
CREATE POLICY "Owners update org" ON public.organizations FOR UPDATE USING (
    id IN (
        SELECT organization_id FROM public.organization_members
        WHERE user_id = auth.uid() AND role = 'owner'
    )
);
-- NOTA: No hay política INSERT. Solo el 'service_role' (Backend) puede crear organizaciones.

-- === PROFILES ===
DROP POLICY IF EXISTS "View own profile" ON public.profiles;
CREATE POLICY "View own profile" ON public.profiles FOR SELECT USING (auth.uid() = id);

DROP POLICY IF EXISTS "Platform Admin View All" ON public.profiles;
CREATE POLICY "Platform Admin View All" ON public.profiles FOR SELECT USING (public.get_is_platform_admin() = true);

-- Permitimos lectura básica para que los usuarios puedan ser encontrados por email al invitar
DROP POLICY IF EXISTS "Public read profiles" ON public.profiles;
CREATE POLICY "Public read profiles" ON public.profiles FOR SELECT USING (true);

-- === ORGANIZATION MEMBERS ===
DROP POLICY IF EXISTS "View team members" ON public.organization_members;
CREATE POLICY "View team members" ON public.organization_members FOR SELECT USING (
    organization_id IN (SELECT public.get_my_org_ids())
);

-- 8. Trigger para nuevos usuarios
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER SECURITY DEFINER SET search_path = public AS $$
DECLARE community_org_id UUID;
BEGIN
  INSERT INTO public.profiles (id, email, full_name, avatar_url, metadata)
  VALUES (new.id, new.email, new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'avatar_url', COALESCE(new.raw_user_meta_data, '{}'::jsonb));

  SELECT id INTO community_org_id FROM public.organizations WHERE type = 'community' LIMIT 1;
  IF community_org_id IS NOT NULL THEN
    INSERT INTO public.organization_members (organization_id, user_id, role, status)
    VALUES (community_org_id, new.id, 'participante', 'active') ON CONFLICT DO NOTHING;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created AFTER INSERT ON auth.users FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();

-- 9. Datos semilla (Bootstrap)
INSERT INTO public.organizations (name, slug, type, settings)
VALUES ('Oasis Community', 'oasis-public', 'community', '{"theme": "default"}'::jsonb)
ON CONFLICT (slug) DO NOTHING;
