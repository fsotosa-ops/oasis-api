-- 1. Limpieza
DELETE FROM auth.users;

-- 2. Inserción de múltiples usuarios para pruebas de OASIS
INSERT INTO auth.users (id, instance_id, aud, role, email, encrypted_password, email_confirmed_at, raw_app_meta_data, raw_user_meta_data, created_at, updated_at, confirmation_token)
VALUES
  -- El Gran Arquitecto (Owner)
  ('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'owner@oasis.com', crypt('password123', gen_salt('bf')), now(), '{"provider":"email","providers":["email"]}', '{"full_name":"Owner Oasis"}', now(), now(), ''),
  -- Un Colaborador/Gestor
  ('00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'gestor@oasis.com', crypt('password123', gen_salt('bf')), now(), '{"provider":"email","providers":["email"]}', '{"full_name":"Gestor Oasis"}', now(), now(), ''),
  -- Un Habitante nuevo (Visitante)
  ('00000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'visitante@oasis.com', crypt('password123', gen_salt('bf')), now(), '{"provider":"email","providers":["email"]}', '{"interest":"resiliencia"}', now(), now(), '');

-- 3. Promover roles manualmente (El trigger por defecto los crea como 'visitante')
UPDATE public.profiles SET role = 'owner' WHERE id = '00000000-0000-0000-0000-000000000001';
UPDATE public.profiles SET role = 'gestor' WHERE id = '00000000-0000-0000-0000-000000000002';
