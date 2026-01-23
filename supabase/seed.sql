-- 1. Limpieza de seguridad (El 'CASCADE' en profiles borrará también los logs y perfiles asociados)
TRUNCATE TABLE auth.users CASCADE;

-- 2. (Opcional) Datos maestros de tu aplicación
-- Si necesitas categorías fijas que borraste por error, puedes ponerlas aquí.
-- Por ahora, como log_categories ya tiene datos en la migración, lo dejamos vacío.
