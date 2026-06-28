-- Migración 004: Crear tabla de configuraciones globales para el contacto

CREATE TABLE IF NOT EXISTS public.settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- Políticas RLS para settings
ALTER TABLE public.settings ENABLE ROW LEVEL SECURITY;

-- Todos los usuarios autenticados pueden leer las settings (necesario para que el cliente lo lea)
CREATE POLICY "todos_leen_settings"
    ON public.settings
    FOR SELECT
    TO authenticated
    USING (true);

-- Solo administradores pueden insertar/actualizar settings
CREATE POLICY "admin_modifica_settings_insert"
    ON public.settings
    FOR INSERT
    TO authenticated
    WITH CHECK (public.is_admin());

CREATE POLICY "admin_modifica_settings_update"
    ON public.settings
    FOR UPDATE
    TO authenticated
    USING (public.is_admin());

-- Otorgar permisos al rol authenticated
GRANT SELECT ON public.settings TO authenticated;
GRANT INSERT, UPDATE ON public.settings TO authenticated;

-- Valor inicial por defecto vacío
INSERT INTO public.settings (key, value) VALUES ('contact_info', '') ON CONFLICT (key) DO NOTHING;
