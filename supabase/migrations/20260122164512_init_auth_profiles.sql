-- supabase/migrations/20260122164512_init_auth_profiles.sql

-- 1. Habilitar extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 2. Limpiar tipos antiguos si existen
DROP TYPE IF EXISTS public.user_role CASCADE;
DROP TYPE IF EXISTS public.org_type CASCADE;

-- 3. Definición de Tipos y Enums
CREATE TYPE public.org_type AS ENUM ('sponsor', 'provider', 'community');
CREATE TYPE public.member_role AS ENUM ('owner', 'admin', 'facilitador', 'participante');
CREATE TYPE public.member_status AS ENUM ('active', 'invited', 'suspended');

-- 4. Tabla de Organizaciones
CREATE TABLE public.organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    type public.org_type NOT NULL DEFAULT 'sponsor',
    settings JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Tabla de Perfiles
CREATE TABLE public.profiles (
    id UUID REFERENCES auth.users ON DELETE CASCADE NOT NULL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    is_platform_admin BOOLEAN DEFAULT false,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Tabla de Miembros
CREATE TABLE public.organization_members (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES public.organizations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    role public.member_role NOT NULL DEFAULT 'participante',
    status public.member_status DEFAULT 'active',
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(organization_id, user_id)
);

-- 7. Seguridad (RLS)
ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organization_members ENABLE ROW LEVEL SECURITY;

-- === [IMPORTANTE] Funciones auxiliares para evitar recursión infinita ===
-- Estas funciones se ejecutan con permisos elevados (SECURITY DEFINER) para
-- leer datos sin disparar las políticas RLS recursivamente.

-- Función A: Verificar si es admin de plataforma
CREATE OR REPLACE FUNCTION public.get_is_platform_admin()
RETURNS BOOLEAN
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT COALESCE(
    (SELECT is_platform_admin FROM public.profiles WHERE id = auth.uid()),
    false
  );
$$;

-- Función B: Obtener IDs de las organizaciones a las que pertenezco
CREATE OR REPLACE FUNCTION public.get_my_org_ids()
RETURNS SETOF UUID
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT organization_id FROM public.organization_members WHERE user_id = auth.uid();
$$;

-- --- POLÍTICAS DE PERFILES ---

-- 1. Ver mi propio perfil
CREATE POLICY "Users can view own profile"
ON public.profiles FOR SELECT USING (auth.uid() = id);

-- 2. Admins ven todo (Usando función segura)
CREATE POLICY "Platform Admins can view all profiles"
ON public.profiles FOR SELECT USING (
    public.get_is_platform_admin() = true
);

-- --- POLÍTICAS DE ORGANIZACIONES ---

-- 3. Ver mis organizaciones (Usando función segura)
CREATE POLICY "Users can view their organizations"
ON public.organizations FOR SELECT USING (
    id IN (SELECT public.get_my_org_ids())
    OR type = 'community'
);

-- --- POLÍTICAS DE MIEMBROS ---

-- 4. Ver miembros de mis organizaciones (Usando función segura)
-- Esto solucionará el error 42P17 actual
CREATE POLICY "Users can view members of their orgs"
ON public.organization_members FOR SELECT USING (
    organization_id IN (SELECT public.get_my_org_ids())
);

-- 8. Trigger de Creación Automática de Usuario
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
SECURITY DEFINER SET search_path = public
AS $$
DECLARE
  community_org_id UUID;
BEGIN
  INSERT INTO public.profiles (id, email, full_name, avatar_url, metadata)
  VALUES (
    new.id,
    new.email,
    new.raw_user_meta_data->>'full_name',
    new.raw_user_meta_data->>'avatar_url',
    COALESCE(new.raw_user_meta_data, '{}'::jsonb)
  );

  SELECT id INTO community_org_id FROM public.organizations WHERE type = 'community' LIMIT 1;

  IF community_org_id IS NOT NULL THEN
    INSERT INTO public.organization_members (organization_id, user_id, role, status)
    VALUES (community_org_id, new.id, 'participante', 'active')
    ON CONFLICT DO NOTHING;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();

-- 9. Insertar la Organización "Comunidad" por defecto
INSERT INTO public.organizations (name, slug, type, settings)
VALUES ('Oasis Community', 'oasis-public', 'community', '{"theme": "default"}'::jsonb)
ON CONFLICT (slug) DO NOTHING;
