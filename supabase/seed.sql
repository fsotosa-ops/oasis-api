INSERT INTO auth.users (id, email, encrypted_password, email_confirmed_at, raw_app_meta_data, raw_user_meta_data, created_at, updated_at, role)
VALUES
  ('00000000-0000-0000-0000-000000000001', 'owner@oasis.com', crypt('password123', gen_salt('bf')), now(), '{"provider":"email"}', '{"full_name":"Owner Oasis"}', now(), now(), 'authenticated'),
  ('00000000-0000-0000-0000-000000000002', 'gestor@oasis.com', crypt('password123', gen_salt('bf')), now(), '{"provider":"email"}', '{"full_name":"Gestor Oasis"}', now(), now(), 'authenticated'),
  ('00000000-0000-0000-0000-000000000003', 'visitante@oasis.com', crypt('password123', gen_salt('bf')), now(), '{"provider":"email"}', '{"interest":"awareness_mental_health"}', now(), now(), 'authenticated');

-- Asignamos los roles en la tabla de perfiles
UPDATE public.profiles SET role = 'owner' WHERE id = '00000000-0000-0000-0000-000000000001';
UPDATE public.profiles SET role = 'gestor' WHERE id = '00000000-0000-0000-0000-000000000002';
