-- ================================================================
-- SCRIPT: Alta manual de usuarios del estudio
-- Proyecto: UTN-FRSF-IA-TP2
--
-- Instrucciones de uso:
--   1. Ir a https://app.supabase.com → tu proyecto
--   2. Authentication → Users → "Add user" → completar email + contraseña
--      (esto crea el registro en auth.users y te da el UUID del usuario)
--   3. Copiar el UUID del usuario recién creado
--   4. Ir a SQL Editor → New query
--   5. Copiar este script, reemplazar los valores y ejecutar
--
-- IMPORTANTE: NO se puede insertar directamente en auth.users desde SQL
-- sin la service key. El paso en el Dashboard es obligatorio.
-- ================================================================


-- ================================================================
-- TEMPLATE: Insertar perfil después de crear el usuario en el Dashboard
-- ================================================================
-- Reemplazar:
--   'UUID-DEL-USUARIO'  → el UUID copiado del Dashboard de Supabase
--   'Juan'              → nombre del cliente
--   'Pérez'             → apellido (opcional, puede ser NULL)
--   '20123456780'       → CUIT sin guiones (11 dígitos), o NULL si no se sabe
--   'monotributo'       → tipo de contribuyente, o NULL si no se sabe
--   'cliente'           → rol: 'cliente' o 'admin'

INSERT INTO public.profiles (id, role, nombre, apellido, cuit, tipo_contribuyente)
VALUES (
    'UUID-DEL-USUARIO',          -- ← reemplazar con el UUID de Auth
    'cliente',                   -- 'cliente' o 'admin'
    'Juan',                      -- nombre (obligatorio)
    'Pérez',                     -- apellido (puede ser NULL)
    '20123456780',               -- CUIT sin guiones (puede ser NULL)
    'monotributo'                -- tipo_contribuyente (puede ser NULL)
)
ON CONFLICT (id) DO UPDATE SET  -- Si el perfil ya existe, actualiza los datos
    role               = EXCLUDED.role,
    nombre             = EXCLUDED.nombre,
    apellido           = EXCLUDED.apellido,
    cuit               = EXCLUDED.cuit,
    tipo_contribuyente = EXCLUDED.tipo_contribuyente,
    updated_at         = NOW();


-- ================================================================
-- EJEMPLOS CONCRETOS: copiar y adaptar según necesidad
-- ================================================================

-- Ejemplo 1: Cliente monotributista con todos los datos
/*
INSERT INTO public.profiles (id, role, nombre, apellido, cuit, tipo_contribuyente)
VALUES (
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'cliente',
    'María',
    'González',
    '27123456780',
    'monotributo'
)
ON CONFLICT (id) DO UPDATE SET
    role = EXCLUDED.role, nombre = EXCLUDED.nombre,
    apellido = EXCLUDED.apellido, cuit = EXCLUDED.cuit,
    tipo_contribuyente = EXCLUDED.tipo_contribuyente, updated_at = NOW();
*/

-- Ejemplo 2: Cliente responsable inscripto sin CUIT cargado todavía
/*
INSERT INTO public.profiles (id, role, nombre, apellido, cuit, tipo_contribuyente)
VALUES (
    'b2c3d4e5-f6a7-8901-bcde-f12345678901',
    'cliente',
    'Carlos',
    'Rodríguez',
    NULL,
    'responsable_inscripto'
)
ON CONFLICT (id) DO UPDATE SET
    role = EXCLUDED.role, nombre = EXCLUDED.nombre,
    apellido = EXCLUDED.apellido, cuit = EXCLUDED.cuit,
    tipo_contribuyente = EXCLUDED.tipo_contribuyente, updated_at = NOW();
*/

-- Ejemplo 3: Usuario administrador (el contador)
/*
INSERT INTO public.profiles (id, role, nombre, apellido, cuit, tipo_contribuyente)
VALUES (
    'c3d4e5f6-a7b8-9012-cdef-123456789012',
    'admin',
    'Contador',
    'Del Estudio',
    NULL,
    NULL
)
ON CONFLICT (id) DO UPDATE SET
    role = EXCLUDED.role, nombre = EXCLUDED.nombre,
    apellido = EXCLUDED.apellido, cuit = EXCLUDED.cuit,
    tipo_contribuyente = EXCLUDED.tipo_contribuyente, updated_at = NOW();
*/


-- ================================================================
-- VERIFICACIÓN: ver todos los usuarios cargados
-- ================================================================

-- Ver todos los perfiles con su email:
SELECT
    p.role,
    p.nombre,
    p.apellido,
    p.cuit,
    p.tipo_contribuyente,
    u.email,
    p.created_at
FROM public.profiles p
JOIN auth.users u ON u.id = p.id
ORDER BY p.role, p.nombre;

-- Ver solo los clientes:
-- SELECT * FROM public.v_clientes;

-- Verificar que un UUID específico existe en auth.users antes de insertar:
-- SELECT id, email, created_at FROM auth.users WHERE id = 'UUID-DEL-USUARIO';
