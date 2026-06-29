-- ================================================================
-- MIGRACIÓN 002: Tabla de perfiles de usuarios
-- Proyecto: UTN-FRSF-IA-TP2
-- Versión: 2.0.0
-- Fecha: 2026-06-28
--
-- Propósito:
--   Extiende auth.users de Supabase con datos propios del estudio:
--   rol, nombre, CUIT, tipo de contribuyente.
--   El rol aquí es la FUENTE DE VERDAD (reemplaza app_metadata).
--
-- Prerequisito:
--   Migración 001 ya ejecutada (extensiones pgvector, tabla documentos).
-- ================================================================


-- ================================================================
-- 1. TABLA: profiles
-- ================================================================

-- Cada fila corresponde a un usuario de auth.users.
-- Se crea automáticamente al insertar un usuario via el script
-- de alta manual (ver sección 4: SCRIPTS DE ALTA DE USUARIOS).

CREATE TABLE IF NOT EXISTS public.profiles (

    -- FK a la tabla interna de Supabase Auth.
    -- ON DELETE CASCADE: si se borra el usuario de Auth, se borra su perfil.
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,

    -- Rol del usuario dentro del sistema.
    -- 'admin'    → contador / administrador del estudio (ve AdminPanel)
    -- 'cliente'  → cliente del estudio (ve el chat con el agente)
    role TEXT NOT NULL DEFAULT 'cliente'
        CHECK (role IN ('admin', 'cliente')),

    -- Datos personales del cliente (opcionales para el admin)
    nombre      TEXT NOT NULL,
    apellido    TEXT,

    -- CUIT sin guiones (11 dígitos). Ej: '20123456780'
    -- NULL permitido: puede completarse en la primera sesión.
    cuit        TEXT CHECK (cuit ~ '^\d{11}$' OR cuit IS NULL),

    -- Categoría fiscal del cliente.
    -- Se pre-carga aquí y también se mantiene en Redis durante la sesión.
    -- NULL = no informado todavía.
    tipo_contribuyente TEXT
        CHECK (tipo_contribuyente IN (
            'monotributo',
            'responsable_inscripto',
            'empleado_relacion_dependencia'
        ) OR tipo_contribuyente IS NULL),

    -- Metadatos
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()

) TABLESPACE pg_default;

COMMENT ON TABLE public.profiles IS
    'Extiende auth.users con datos propios del estudio: rol, nombre, CUIT, tipo de contribuyente. '
    'Fuente de verdad para el rol (reemplaza app_metadata de Supabase Auth). '
    'Relación 1:1 con auth.users via FK en id.';

COMMENT ON COLUMN public.profiles.role IS
    'Rol del usuario: admin (contador) o cliente. Determina qué pantalla ve al loguearse.';

COMMENT ON COLUMN public.profiles.cuit IS
    'CUIT sin guiones, 11 dígitos. Ej: 20123456780. Se valida con regex.';

COMMENT ON COLUMN public.profiles.tipo_contribuyente IS
    'Categoría fiscal del cliente. Puede ser NULL si no fue informada. '
    'Se sincroniza con la clave Redis perfil:{user_id} durante las sesiones.';


-- ================================================================
-- 2. ÍNDICES
-- ================================================================

-- Búsquedas por rol (el backend filtra por role='cliente' para listar clientes)
CREATE INDEX IF NOT EXISTS idx_profiles_role
    ON public.profiles (role);

-- Búsquedas por CUIT
CREATE INDEX IF NOT EXISTS idx_profiles_cuit
    ON public.profiles (cuit)
    WHERE cuit IS NOT NULL;


-- ================================================================
-- 3. TRIGGER: actualizar updated_at automáticamente
-- ================================================================

CREATE OR REPLACE FUNCTION public.update_profiles_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_profiles_updated_at ON public.profiles;
CREATE TRIGGER trigger_profiles_updated_at
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW
    EXECUTE FUNCTION public.update_profiles_updated_at();


-- ================================================================
-- 4. ROW LEVEL SECURITY (RLS)
-- ================================================================

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- Los clientes solo pueden leer su propio perfil
CREATE POLICY "cliente_lee_su_perfil"
    ON public.profiles
    FOR SELECT
    TO authenticated
    USING (auth.uid() = id);

-- Los clientes pueden actualizar su propio perfil
-- (útil si en el futuro se agrega un formulario de edición)
CREATE POLICY "cliente_actualiza_su_perfil"
    ON public.profiles
    FOR UPDATE
    TO authenticated
    USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id);

-- Función segura para verificar si el usuario actual es admin (bypassea RLS para evitar recursión)
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN
LANGUAGE sql SECURITY DEFINER
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.profiles 
        WHERE id = auth.uid() AND role = 'admin'
    );
$$;

-- Los admins pueden leer todos los perfiles
CREATE POLICY "admin_lee_todos"
    ON public.profiles
    FOR SELECT
    TO authenticated
    USING (public.is_admin());

-- Los admins pueden insertar y actualizar cualquier perfil
CREATE POLICY "admin_inserta_actualiza"
    ON public.profiles
    FOR ALL
    TO authenticated
    USING (public.is_admin());

-- El service_role (backend con SUPABASE_SERVICE_KEY) puede hacer todo sin restricciones.
-- Supabase bypassa RLS automáticamente para service_role — no hace falta policy explícita.


-- ================================================================
-- 5. PERMISOS
-- ================================================================

GRANT SELECT, UPDATE ON public.profiles TO authenticated;


-- ================================================================
-- 6. VISTA ÚTIL: listado de clientes para el admin
-- ================================================================

-- El AdminPanel puede usar esta vista para mostrar la lista de clientes registrados.
CREATE OR REPLACE VIEW public.v_clientes AS
    SELECT
        p.id,
        u.email,
        p.nombre,
        p.apellido,
        p.cuit,
        p.tipo_contribuyente,
        p.created_at
    FROM public.profiles p
    JOIN auth.users u ON u.id = p.id
    WHERE p.role = 'cliente'
    ORDER BY p.created_at DESC;

COMMENT ON VIEW public.v_clientes IS
    'Listado de todos los clientes del estudio con sus datos de Auth y perfil. '
    'Consultar desde el AdminPanel para mostrar la lista de clientes.';


-- ================================================================
-- 7. VERIFICACIÓN POST-INSTALACIÓN
-- ================================================================

-- Ejecutar estos queries para verificar que la migración funcionó:

-- 1. Ver tabla creada:
-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'profiles' AND table_schema = 'public'
-- ORDER BY ordinal_position;

-- 2. Ver políticas RLS:
-- SELECT policyname, cmd, roles FROM pg_policies WHERE tablename = 'profiles';

-- 3. Ver índices:
-- SELECT indexname FROM pg_indexes WHERE tablename = 'profiles';

-- 4. Ver vista:
-- SELECT * FROM v_clientes;  -- vacío hasta que haya usuarios
