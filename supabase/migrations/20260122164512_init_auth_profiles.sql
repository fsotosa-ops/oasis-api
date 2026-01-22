CREATE EXTENSION IF NOT EXISTS pgcrypto;
-- 1. Definición de Roles (Matriz Oasis)
-- 'visitante' es el rol base para awareness y recursos gratuitos
CREATE TYPE user_role AS ENUM ('owner', 'admin', 'gestor', 'participante', 'visitante');

-- 2. Tabla de Perfiles Limpia
CREATE TABLE public.profiles (
    id UUID REFERENCES auth.users ON DELETE CASCADE NOT NULL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    role user_role DEFAULT 'visitante' NOT NULL,
    -- Usamos metadata para guardar cualquier dato extra sin ensuciar el esquema
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Seguridad (RLS)
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- Política: Los usuarios pueden leer su propio perfil para que la API valide el rol
CREATE POLICY "Users can view own profile"
ON public.profiles FOR SELECT
USING (auth.uid() = id);

-- Política: Owner y Admin pueden ver todo
CREATE POLICY "Privileged roles can view all"
ON public.profiles FOR SELECT
USING (
  EXISTS (
    SELECT 1 FROM public.profiles
    WHERE id = auth.uid() AND role IN ('owner', 'admin')
  )
);

-- 4. Trigger de Creación Automática (Ajustado)
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, email, role, metadata)
  VALUES (
    new.id,
    new.email,
    'visitante'::user_role, -- Casteo explícito al tipo Enum
    COALESCE(new.raw_user_meta_data, '{}'::jsonb)
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();
