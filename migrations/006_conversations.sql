-- migration: 006_conversations
-- descripción: Crea tabla de conversaciones para agrupar mensajes de chat y permitir sidebars.

CREATE TABLE IF NOT EXISTS public.conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'Nueva Conversación',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Habilitar RLS
ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Clientes pueden ver sus conversaciones"
    ON public.conversations FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Clientes pueden insertar sus conversaciones"
    ON public.conversations FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Clientes pueden actualizar sus conversaciones"
    ON public.conversations FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Administradores pueden ver todas las conversaciones"
    ON public.conversations FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.profiles
            WHERE profiles.id = auth.uid() AND profiles.role = 'admin'
        )
    );

-- Modificar chat_messages para agregar conversation_id
ALTER TABLE public.chat_messages ADD COLUMN conversation_id UUID REFERENCES public.conversations(id) ON DELETE CASCADE;

-- Crear conversaciones por defecto para mensajes huérfanos
DO $$
DECLARE
    rec RECORD;
    conv_id UUID;
BEGIN
    FOR rec IN SELECT DISTINCT user_id FROM public.chat_messages WHERE conversation_id IS NULL LOOP
        INSERT INTO public.conversations (user_id, title) VALUES (rec.user_id, 'Conversación antigua') RETURNING id INTO conv_id;
        UPDATE public.chat_messages SET conversation_id = conv_id WHERE user_id = rec.user_id AND conversation_id IS NULL;
    END LOOP;
END $$;

-- Ahora que todos los existentes tienen ID, lo marcamos como NOT NULL
ALTER TABLE public.chat_messages ALTER COLUMN conversation_id SET NOT NULL;
