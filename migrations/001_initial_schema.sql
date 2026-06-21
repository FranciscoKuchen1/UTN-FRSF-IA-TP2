-- ================================================================
-- MIGRACIÓN: Estructura base para Agente Asistente Estudio Contable
-- Proyecto: UTN-FRSF-IA-TP2-2.0.0
-- Versión: 1.0.0
-- Fecha: 2026-06-20
-- ================================================================

-- ================================================================
-- 1. EXTENSIONES REQUERIDAS
-- ================================================================

-- pgvector: permite almacenar y buscar embeddings vectoriales
-- Requerido por: rag/retriever.py (búsqueda semántica en documentos)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- Para búsqueda full-text
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;  -- Para búsquedas aproximadas

-- ================================================================
-- 2. TABLA: documentos (RAG - Retrieval Augmented Generation)
-- ================================================================

-- Almacena fragmentos de documentos (chunks) con sus embeddings
-- para búsqueda semántica usando vector similarity search
--
-- Relación con código:
--   - rag/ingest.py: INSERT (línea 46-49)
--   - rag/retriever.py: RPC match_documentos (línea 32-45)
--   - agent/tools.py: buscar_en_documentos (línea 51)

CREATE TABLE IF NOT EXISTS public.documentos (
    -- Identificadores
    id BIGSERIAL PRIMARY KEY,
    
    -- Contenido
    content TEXT NOT NULL,  -- Fragmento del documento
    source TEXT NOT NULL,   -- Nombre del archivo/origen (ej: "Calendario AFIP 2026")
    chunk_index INTEGER,    -- Índice secuencial del chunk dentro del documento
    
    -- Embeddings vectoriales (Google gemini-embedding-2 usa 3072 dimensiones)
    embedding vector(3072) NOT NULL,  -- Vector de embeddings para búsqueda semántica
    
    -- Metadata y timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
) TABLESPACE pg_default;

-- Índice de búsqueda primaria: búsqueda por similarity vectorial
-- Tipo: Sin índice (búsqueda secuencial)
-- Razón: pgvector solo soporta IVFFLAT/HNSW hasta 2000 dims, pero Gemini genera 3072
-- Solución: Búsqueda secuencial con operador <=> (correcta, algo más lenta)
-- 
-- Para optimizar después:
-- - Opción 1: Usar PCA en la app para reducir a 1500 dims + HNSW
-- - Opción 2: Cambiar a modelo con menor dimensionalidad
-- - Opción 3: Escalar verticalmente o usar búsqueda externa
--
-- Por ahora: búsqueda secuencial funciona correctamente sin límites de dimensionalidad

-- NO CREAR ÍNDICE VECTORIAL (incompatible con 3072 dims)
-- La función RPC hará búsqueda secuencial

-- Índice secundario: búsqueda por fuente (origen del documento)
-- Para queries como: SELECT * FROM documentos WHERE source = 'Calendario AFIP 2026'
CREATE INDEX IF NOT EXISTS idx_documentos_source
    ON public.documentos (source);

-- Índice terciario: búsqueda full-text en contenido
-- Para búsquedas simples por palabras clave en el contenido
CREATE INDEX IF NOT EXISTS idx_documentos_content_fulltext
    ON public.documentos USING GIN (to_tsvector('spanish', content));

-- Índice para ordenamiento temporal
CREATE INDEX IF NOT EXISTS idx_documentos_created_at
    ON public.documentos (created_at DESC);

-- ================================================================
-- 3. FUNCIÓN RPC: match_documentos (Búsqueda semántica)
-- ================================================================

-- Función SQL que busca documentos similares a un embedding de query
-- Parámetros:
--   query_embedding: vector(3072) - embedding generado desde la consulta del usuario
--   match_threshold: float - similitud mínima (0 a 1, default 0.7)
--   match_count: int - máximo de resultados a retornar (default 10)
--
-- Retorna:
--   - id, content, source, chunk_index, similarity
--   - Ordenado por similitud descendente
--
-- Uso en código:
--   rag/retriever.py línea 32-45:
--     response = supabase.rpc("match_documentos", {...}).execute()
--
-- Ejemplo de uso directo:
--   SELECT * FROM match_documentos(
--       query_embedding => CAST('[-0.1, 0.2, ..., 0.5]' AS vector),
--       match_threshold => 0.7,
--       match_count => 3
--   );

CREATE OR REPLACE FUNCTION public.match_documentos(
    query_embedding vector,
    match_threshold float DEFAULT 0.7,
    match_count int DEFAULT 10
)
RETURNS TABLE (
    id bigint,
    content text,
    source text,
    chunk_index int,
    similarity float
)
LANGUAGE sql STABLE SECURITY DEFINER
AS $$
    SELECT
        documentos.id,
        documentos.content,
        documentos.source,
        documentos.chunk_index,
        -- Calcula similitud del coseno (1 - distancia coseno)
        -- Rango: 0 (totalmente opuesto) a 1 (idéntico)
        (1 - (documentos.embedding <=> query_embedding))::float AS similarity
    FROM public.documentos
    WHERE 
        -- Filtro por umbral de similitud
        (1 - (documentos.embedding <=> query_embedding)) > match_threshold
    ORDER BY
        similarity DESC
    LIMIT match_count;
$$;

-- ================================================================
-- 4. FUNCIÓN: actualizar_timestamp_documentos
-- ================================================================

-- Trigger que actualiza automáticamente el campo updated_at
-- cuando se modifica un registro

CREATE OR REPLACE FUNCTION public.update_documentos_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Aplicar trigger automáticamente
DROP TRIGGER IF EXISTS trigger_documentos_updated_at ON public.documentos;
CREATE TRIGGER trigger_documentos_updated_at
    BEFORE UPDATE ON public.documentos
    FOR EACH ROW
    EXECUTE FUNCTION public.update_documentos_updated_at();

-- ================================================================
-- 5. POLÍTICAS DE SEGURIDAD (Row Level Security - RLS)
-- ================================================================

-- Habilitar RLS en tabla documentos
ALTER TABLE public.documentos ENABLE ROW LEVEL SECURITY;

-- Política: Permitir lectura a usuarios autenticados (agente)
CREATE POLICY "allow_read_authenticated"
    ON public.documentos
    FOR SELECT
    TO authenticated
    USING (true);

-- Política: Permitir lectura a usuarios anónimos (consultas públicas)
CREATE POLICY "allow_read_anonymous"
    ON public.documentos
    FOR SELECT
    TO anon
    USING (true);

-- Política: Permitir inserción a usuarios autenticados (ingestión de documentos)
CREATE POLICY "allow_insert_authenticated"
    ON public.documentos
    FOR INSERT
    TO authenticated
    WITH CHECK (true);

-- Política: Permitir actualización a usuarios autenticados
CREATE POLICY "allow_update_authenticated"
    ON public.documentos
    FOR UPDATE
    TO authenticated
    USING (true)
    WITH CHECK (true);

-- Política: Permitir eliminación a usuarios autenticados
CREATE POLICY "allow_delete_authenticated"
    ON public.documentos
    FOR DELETE
    TO authenticated
    USING (true);

-- ================================================================
-- 6. PERMISOS Y ACCESOS
-- ================================================================

-- Permisos sobre tabla documentos
GRANT SELECT ON public.documentos TO authenticated;
GRANT SELECT ON public.documentos TO anon;
GRANT INSERT ON public.documentos TO authenticated;
GRANT UPDATE ON public.documentos TO authenticated;
GRANT DELETE ON public.documentos TO authenticated;

-- Permisos para secuencia (auto-increment del id)
GRANT USAGE ON SEQUENCE public.documentos_id_seq TO authenticated;

-- Permisos sobre función RPC match_documentos
GRANT EXECUTE ON FUNCTION public.match_documentos TO authenticated;
GRANT EXECUTE ON FUNCTION public.match_documentos TO anon;

-- ================================================================
-- 7. VISTAS ÚTILES (Opcional - para debugging)
-- ================================================================

-- Vista: Estadísticas de documentos ingestados
CREATE OR REPLACE VIEW public.v_documentos_stats AS
    SELECT
        source,
        COUNT(*) as total_chunks,
        COUNT(DISTINCT chunk_index) as unique_indices,
        MIN(created_at) as first_indexed,
        MAX(updated_at) as last_updated,
        ROUND((SUM(LENGTH(content))::numeric / 1024)::numeric, 2) as size_kb
    FROM public.documentos
    GROUP BY source
    ORDER BY total_chunks DESC;

-- Vista: Documentos por fecha de ingesta
CREATE OR REPLACE VIEW public.v_documentos_timeline AS
    SELECT
        DATE(created_at) as ingestion_date,
        source,
        COUNT(*) as chunks_added
    FROM public.documentos
    GROUP BY DATE(created_at), source
    ORDER BY ingestion_date DESC, chunks_added DESC;

-- ================================================================
-- 8. COMENTARIOS DE DOCUMENTACIÓN
-- ================================================================

COMMENT ON TABLE public.documentos IS
    'Almacena fragmentos de documentos (chunks) con sus embeddings vectoriales. Utilizado por el sistema RAG para búsqueda semántica de información. Mantiene los documentos fragmentados del estudio contable (normativas, calendarios fiscales, guías, etc.) para que el agente pueda recuperar información relevante mediante similitud vectorial.';

COMMENT ON COLUMN public.documentos.id IS
    'Identificador único auto-generado del chunk de documento';

COMMENT ON COLUMN public.documentos.content IS
    'Texto del fragmento del documento (típicamente 500 palabras con overlap)';

COMMENT ON COLUMN public.documentos.source IS
    'Nombre del documento de origen (ej: "Calendario AFIP 2026", "Normativa IVA")';

COMMENT ON COLUMN public.documentos.chunk_index IS
    'Índice secuencial del chunk dentro del documento original (0, 1, 2, ...)';

COMMENT ON COLUMN public.documentos.embedding IS
    'Vector de 3072 dimensiones generado por Google Gemini Embedding 2 model';

COMMENT ON COLUMN public.documentos.created_at IS
    'Timestamp de cuando se ingestó el chunk a la base de datos';

COMMENT ON COLUMN public.documentos.updated_at IS
    'Timestamp de la última modificación del registro (actualizado automáticamente)';

COMMENT ON FUNCTION public.match_documentos IS
    'Busca chunks de documentos similares a un embedding de query usando similitud del coseno. Retorna los top K resultados ordenados por similitud descendente, filtrados por umbral mínimo.';

COMMENT ON INDEX public.idx_documentos_source IS
    'Índice para filtrado rápido por fuente de documento.';

COMMENT ON INDEX public.idx_documentos_content_fulltext IS
    'Índice GIN para búsqueda full-text en español del contenido del documento.';

-- ================================================================
-- 9. RESUMEN DE DEPENDENCIAS
-- ================================================================

/*
DEPENDENCIAS DE LA APLICACIÓN:

1. agent/core.py → agent/tools.py
   - Ejecuta herramienta "buscar_en_documentos"

2. agent/tools.py → rag/retriever.py
   - Llama a buscar_similar(query, top_k=3)

3. rag/retriever.py → Supabase
   - Llama RPC match_documentos
   - Requiere tabla: documentos
   - Requiere función: match_documentos
   - Requiere extensión: pgvector

4. rag/ingest.py → Supabase
   - INSERT en tabla documentos
   - Requiere tabla: documentos
   - Requiere extensión: pgvector

5. agent/memory.py → Redis (opcional)
   - Almacena perfil:{cliente_id}
   - NO requiere cambios en Supabase
   - Backend configurable: redis | memory

NOTA: 
- Langfuse NO requiere cambios en base de datos
- Frontend NO requiere cambios en base de datos
- API NO almacena estado en base de datos (usa memoria en proceso)
*/

-- ================================================================
-- 10. VERIFICACIÓN DE INSTALACIÓN
-- ================================================================

-- Ejecutar estos queries después de la migración para verificar:

-- Ver tablas creadas
-- SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';

-- Ver funciones creadas
-- SELECT routine_name FROM information_schema.routines WHERE routine_schema = 'public';

-- Ver índices creados
-- SELECT indexname FROM pg_indexes WHERE schemaname = 'public' AND tablename = 'documentos';

-- Ver extensiones habilitadas
-- SELECT extname FROM pg_extension WHERE extname IN ('vector', 'pg_trgm', 'fuzzystrmatch');

-- Probar función (requiere tener datos en documentos)
-- SELECT * FROM match_documentos(
--     query_embedding => CAST('[0.1, 0.2, ..., 0.3]'::vector(3072)),
--     match_threshold => 0.7,
--     match_count => 3
-- ) LIMIT 3;
