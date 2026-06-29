-- migration: 005_chat_messages
-- descripción: Crea la tabla para persistir historiales de chat y sus políticas de seguridad (RLS).

CREATE TABLE IF NOT EXISTS public.chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Habilitar RLS
ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;

-- Políticas para clientes: solo pueden leer y crear sus propios mensajes
CREATE POLICY "Clientes pueden ver sus propios mensajes"
    ON public.chat_messages FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Clientes pueden insertar sus propios mensajes"
    ON public.chat_messages FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Políticas para administradores: pueden ver todos los mensajes
CREATE POLICY "Administradores pueden ver todos los mensajes"
    ON public.chat_messages FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.profiles
            WHERE profiles.id = auth.uid() AND profiles.role = 'admin'
        )
    );
