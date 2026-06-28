-- ================================================================
-- MIGRACIÓN 003: Tabla de derivaciones a contador (Escalations)
-- ================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS public.escalations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    original_query TEXT NOT NULL,
    summary TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'resolved')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE
);

COMMENT ON TABLE public.escalations IS
    'Tickets de derivación generados por el agente cuando no puede responder.';

-- Políticas RLS (Row Level Security)
ALTER TABLE public.escalations ENABLE ROW LEVEL SECURITY;

-- Clientes pueden leer sus propios tickets
CREATE POLICY "cliente_lee_sus_tickets"
    ON public.escalations
    FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

-- Admins pueden leer todos los tickets (usando la función is_admin de la migración 002)
CREATE POLICY "admin_lee_todos_tickets"
    ON public.escalations
    FOR SELECT
    TO authenticated
    USING (public.is_admin());

-- Admins pueden actualizar tickets
CREATE POLICY "admin_actualiza_tickets"
    ON public.escalations
    FOR UPDATE
    TO authenticated
    USING (public.is_admin());

-- Insertar tickets (backend lo hace con service_role, bypasses RLS)

-- Otorga permisos
GRANT SELECT ON public.escalations TO authenticated;
GRANT UPDATE ON public.escalations TO authenticated;
