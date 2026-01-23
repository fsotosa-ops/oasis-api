-- supabase/migrations/20260122164512_init_auth_profiles.sql

-- 1. Habilitar extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 2. Limpiar tipos antiguos si existen (para evitar conflictos en development)
DROP TYPE IF EXISTS public.user_role CASCADE;
DROP TYPE IF EXISTS public.org_type CASCADE;

-- 3. Definición de Tipos y Enums
CREATE TYPE public.org_type AS ENUM ('sponsor', 'provider', 'community');
CREATE TYPE public.member_role AS ENUM ('owner', 'admin', 'facilitador', 'participante');
CREATE TYPE public.member_status AS ENUM ('active', 'invited', 'suspended');

-- 4. Tabla de Organizaciones (Los "Tenants")
CREATE TABLE public.organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL, -- Ej: 'banco-estado', 'oasis-community'
    type public.org_type NOT NULL DEFAULT 'sponsor',
    settings JSONB DEFAULT '{}'::jsonb, -- Configuración visual (logo, colores)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Tabla de Perfiles (Identidad Única)
-- Nota: Ya no tiene 'role' ni 'organization_id'
CREATE TABLE public.profiles (
    id UUID REFERENCES auth.users ON DELETE CASCADE NOT NULL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    is_platform_admin BOOLEAN DEFAULT false, -- Solo para el equipo interno de Oasis (Super Admins)
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Tabla de Miembros (Relación Usuario <-> Organización)
CREATE TABLE public.organization_members (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES public.organizations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,

    role public.member_role NOT NULL DEFAULT 'participante',
    status public.member_status DEFAULT 'active',

    joined_at TIMESTAMPTZ DEFAULT NOW(),

    -- Restricción: Un usuario solo puede tener un rol por organización
    UNIQUE(organization_id, user_id)
);

-- 7. Seguridad (RLS - Row Level Security)
ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organization_members ENABLE ROW LEVEL SECURITY;

-- POLÍTICAS DE PERFILES
-- Todos pueden ver su propio perfil
CREATE POLICY "Users can view own profile"
ON public.profiles FOR SELECT USING (auth.uid() = id);

-- Los Platform Admins pueden ver todo
CREATE POLICY "Platform Admins can view all profiles"
ON public.profiles FOR SELECT USING (
    (SELECT is_platform_admin FROM public.profiles WHERE id = auth.uid()) = true
);

-- POLÍTICAS DE ORGANIZACIONES
-- Un usuario puede ver las organizaciones a las que pertenece
CREATE POLICY "Users can view their organizations"
ON public.organizations FOR SELECT USING (
    EXISTS (
        SELECT 1 FROM public.organization_members
        WHERE organization_id = public.organizations.id
        AND user_id = auth.uid()
    )
    OR type = 'community' -- La comunidad es pública para lectura básica
);

-- POLÍTICAS DE MIEMBROS
-- Un usuario puede ver quiénes son sus compañeros en su organización
CREATE POLICY "Users can view members of their orgs"
ON public.organization_members FOR SELECT USING (
    organization_id IN (
        SELECT organization_id FROM public.organization_members
        WHERE user_id = auth.uid()
    )
);

-- 8. Trigger de Creación Automática de Usuario y Asignación a Comunidad
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
SECURITY DEFINER SET search_path = public
AS $$
DECLARE
  community_org_id UUID;
BEGIN
  -- A. Insertar el Perfil Base
  INSERT INTO public.profiles (id, email, full_name, avatar_url, metadata)
  VALUES (
    new.id,
    new.email,
    new.raw_user_meta_data->>'full_name',
    new.raw_user_meta_data->>'avatar_url',
    COALESCE(new.raw_user_meta_data, '{}'::jsonb)
  );

  -- B. Lógica de "Visitante" -> Asignar a "Oasis Community" por defecto
  -- Buscamos si existe la organización tipo comunidad
  SELECT id INTO community_org_id FROM public.organizations WHERE type = 'community' LIMIT 1;

  -- Si existe, creamos la membresía automática
  IF community_org_id IS NOT NULL THEN
    INSERT INTO public.organization_members (organization_id, user_id, role, status)
    VALUES (community_org_id, new.id, 'participante', 'active')
    ON CONFLICT DO NOTHING; -- Evitar errores si ya existe
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();

-- 9. Insertar la Organización "Comunidad" por defecto (Bootstrap)
-- Esto asegura que el trigger anterior funcione desde el día 1
INSERT INTO public.organizations (name, slug, type, settings)
VALUES ('Oasis Community', 'oasis-public', 'community', '{"theme": "default"}'::jsonb)
ON CONFLICT (slug) DO NOTHING;
