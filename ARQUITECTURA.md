# Análisis de Arquitectura - UTN-FRSF-IA-TP2

## 📋 Resumen Ejecutivo

**Agente conversacional** basado en **ReAct** que responde consultas fiscales de clientes de un estudio contable. Utiliza:
- **LLM**: Google Gemini 3.5 Flash (IA generativa)
- **RAG**: Supabase pgvector (búsqueda semántica en documentos)
- **Memoria**: Redis Cloud (perfil persistente del cliente)
- **Backend**: FastAPI (Python)
- **Frontend**: React + Vite

---

## 🏗️ Arquitectura de Datos

### 1. **Supabase (PostgreSQL + pgvector)**

| Componente | Propósito | Línea de Código | Estructura |
|-----------|----------|-----------------|-----------|
| Tabla `documentos` | Almacenar fragmentos (chunks) de documentos con embeddings vectoriales | `rag/ingest.py:46` | id, content, source, chunk_index, embedding, created_at, updated_at |
| Función RPC `match_documentos()` | Búsqueda semántica usando similitud coseno | `rag/retriever.py:32` | query_embedding → match_threshold → match_count |
| Índice IVFFLAT | Acelerar búsquedas vectoriales en alta dimensionalidad | SQL: `CREATE INDEX ... vector_cosine_ops` | Lists=100 |
| Extensión `pgvector` | Soporte nativo para vectores de 768 dimensiones | SQL: `CREATE EXTENSION vector` | - |

**Flujo de datos RAG:**
```
User asks a question
    ↓
agent/tools.py:search_documents()
    ↓
rag/retriever.py:search_similar(query)
    ↓
embed_query() → nomic-embed-text-v1_5 → vector(768)
    ↓
supabase.rpc("match_documentos", {...})
    ↓
PostgreSQL vector similarity query
    ↓
Returns top-3 most relevant documents
    ↓
Agent includes retrieved context in the LLM prompt
```

### 2. **Redis Cloud (Memoria a Largo Plazo)**

| Componente | Propósito | Línea de Código | Estructura |
|-----------|----------|-----------------|-----------|
| Key-value `profile:{client_id}` | Persist taxpayer type between sessions | `agent/memory.py:73-79` | `{"taxpayer_type": "monotributo"}` |
| TTL: 7 days | Automatic expiration of old data | `agent/memory.py:76` | setex(..., 86400*7) |
| Configurable backend | Use Redis or in-memory according to MEMORY_BACKEND | `agent/memory.py:43-65` | "redis" \| "memory" |

**Flujo de memoria:**
```
User: "I am a monotributo taxpayer"
    ↓
agent/core.py:_extract_and_save_profile()
    ↓
memory.update_taxpayer_type()
    ↓
Redis SET profile:session-123 '{"taxpayer_type":"monotributo"}'
    ↓
(7 days later it expires automatically)
    ↓
Next session: memory.get_profile() → retrieves data
```

### 3. **Frontend (React - sin BD)**

| Componente | Propósito | Almacenamiento |
|-----------|----------|-----------------|
| `sessionId` | Identificador único de sesión | localStorage del navegador |
| `messages` | Historial de chat | Estado en memoria (se pierde al cerrar) |
| `input` | Texto ingresado por usuario | Estado en memoria |

El frontend NO almacena datos en base de datos. Todo es temporal.

### 4. **API Backend (FastAPI - sin BD)**

| Componente | Propósito | Almacenamiento |
|-----------|----------|-----------------|
| `_agents` dict | Cache de agentes por sesión | Memoria del proceso Python (se pierde al reiniciar) |

El backend mantiene agentes en RAM. En producción, necesitaría Redis para compartir agentes entre múltiples instancias.

---

## 🔄 Flujo Completo: De Pregunta a Respuesta

```
FRONTEND (React)
    ↓ POST /chat {session_id, message}
API (FastAPI)
    ↓ Crea o recupera ReActAgent
AGENT (core.py)
    ├─ _build_system() → Arma sistema prompt con tipo de contribuyente de Redis
    ├─ _call_llm() → Llama Gemini con contexto
    └─ _parse_action() → Extrae tool name del output
        ↓
TOOLS (tools.py)
    ├─ search_documents()
    │   ↓
    │   RAG (retriever.py)
    │   ├─ embed_query() → nomic embedding
    │   ├─ search_similar() → RPC match_documentos in Supabase
    │   └─ Returns top-3 documents
    │
    ├─ get_due_dates() → hardcoded table in tools.py
    ├─ escalate_query() → Print + (TODO: webhook)
    └─ get_current_datetime() → datetime.now()
        ↓
MEMORY (memory.py)
    ├─ short_mem.add() → Agregar a historial sesión
    └─ long_mem.guardar_perfil() → Redis
        ↓
RESPONSE
    └─ Respuesta del agente → Frontend
```

---

## 📊 Modelo de Datos Detallado

### Tabla: `documentos` (Supabase)

```sql
-- Estructura física en PostgreSQL
id              BIGSERIAL PRIMARY KEY
content         TEXT NOT NULL           -- Chunk de ~500 palabras
source          TEXT NOT NULL           -- "Calendario AFIP 2026"
chunk_index     INTEGER                 -- 0, 1, 2, ...
embedding       vector(768)             -- De Google text-embedding-004
created_at      TIMESTAMP DEFAULT NOW() -- Cuándo se ingestó
updated_at      TIMESTAMP               -- Última modificación

-- Índices
idx_documentos_embedding_ivfflat   -- Búsqueda vectorial rápida
idx_documentos_source              -- Filtrar por fuente
idx_documentos_content_fulltext    -- Búsqueda por palabras clave
idx_documentos_created_at          -- Ordenar por fecha

-- RLS Policies (Row Level Security)
- allow_read_authenticated          -- Agente puede leer
- allow_read_anonymous              -- API pública puede leer
- allow_insert_authenticated        -- Ingestión autorizada
- allow_update_authenticated        -- Actualización autorizada
- allow_delete_authenticated        -- Eliminación autorizada
```

### Redis: `perfil:{cliente_id}` (JSON)

```redis
-- Estructura en Redis Cloud
KEY: perfil:web-abc123def456
VALUE: {
    "tipo_contribuyente": "monotributo",
    "fecha_guardado": "2026-06-20T15:30:00",
    ...
}
TTL: 604800 segundos (7 días)
```

---

## 🔐 Seguridad y Permisos

### Supabase RLS (Row Level Security)

```
┌─────────────────────────────────────────┐
│         Rol: authenticated              │
│  (Agente + scripts de ingestión)        │
├─────────────────────────────────────────┤
│ SELECT: ✓ (leer documentos)             │
│ INSERT: ✓ (ingestar)                    │
│ UPDATE: ✓ (actualizar)                  │
│ DELETE: ✓ (eliminar)                    │
│ EXECUTE match_documentos: ✓             │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│           Rol: anon (public)            │
│    (Consultas públicas opcionales)      │
├─────────────────────────────────────────┤
│ SELECT: ✓ (leer documentos)             │
│ INSERT: ✗ (no puede ingestar)           │
│ UPDATE: ✗ (no puede editar)             │
│ DELETE: ✗ (no puede eliminar)           │
│ EXECUTE match_documentos: ✓             │
└─────────────────────────────────────────┘
```

### Variables de Entorno Requeridas

```env
# API Keys
GROQ_API_KEY=xxx                         # Groq API key
LANGFUSE_SECRET_KEY=sk-lf-xxx           # Observabilidad (opcional)
LANGFUSE_PUBLIC_KEY=pk-lf-xxx           # Observabilidad (opcional)

# Supabase (RAG)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=sb_xxx

# Redis (Memoria a largo plazo)
MEMORY_BACKEND=redis                     # "redis" | "memory"
REDIS_URL=rediss://default:pwd@host:port

# Groq
LLM_MODEL=qwen/qwen3-32b       # Model actual

# Configuración
MAX_REACT_ITERATIONS=5
SIMILARITY_THRESHOLD=0.7
FRONTEND_ORIGIN=http://localhost:5173
```

---

## 📈 Dependencias Entre Componentes

```
frontend/App.jsx
    │
    └─→ POST /chat → api/main.py
            │
            └─→ ReActAgent() → agent/core.py
                    │
                    ├─→ _call_llm() → Google Gemini API
                    ├─→ _parse_action()
                    │
                        └─→ execute_tool() → agent/tools.py
                            │
                            ├─→ search_documents()
                            │   └─→ rag/retriever.py
                            │       ├─→ embed_query() → nomic API
                            │       └─→ search_similar()
                            │           └─→ Supabase RPC match_documentos()
                            │
                            ├─→ get_due_dates()
                            ├─→ escalate_query()
                            └─→ get_current_datetime()
                    │
                    └─→ memory.py
                        ├─→ ShortTermMemory (en sesión)
                        └─→ LongTermMemory (Redis)
                            └─→ Redis Cloud

Observabilidad opcional:
    └─→ observability/logger.py
        └─→ Langfuse API
```

---

## 🚀 Ciclo de Vida: Ingestión de Documentos

```
1. PREPARACIÓN
   python -m rag.ingest --file docs/calendario_afip.txt --source "Calendario AFIP 2026"

2. LECTURA
   rag/ingest.py:ingest_document()
   → open(file_path) → lee contenido

3. FRAGMENTACIÓN
   chunk_text(text, chunk_size=500, overlap=50)
   → Divide en palabras → agrupa en chunks

4. EMBEDDING
   Para cada chunk:
   → embed_text() → Google text-embedding-004
   → Genera vector(768)

5. ALMACENAMIENTO
   supabase.table("documentos").insert({
       "content": chunk,
       "source": "Calendario AFIP 2026",
       "chunk_index": 0,
       "embedding": [0.1, -0.2, ..., 0.5]
   }).execute()

6. INDEXACIÓN
   PostgreSQL crea automáticamente índice IVFFLAT
   para búsqueda vectorial rápida
```

---

## 📝 Migración SQL

El archivo `migrations/001_initial_schema.sql` contiene:

✅ Extensiones (pgvector, pg_trgm, fuzzystrmatch)
✅ Tabla `documentos` con esquema completo
✅ Índices (IVFFLAT, source, fulltext, created_at)
✅ Función RPC `match_documentos()`
✅ Triggers para updated_at automático
✅ Row Level Security (RLS) policies
✅ Permisos y grants
✅ Vistas para estadísticas
✅ Comentarios de documentación

**Cómo ejecutar:**
1. Ve a https://app.supabase.com
2. SQL Editor → New query
3. Copiar contenido de `migrations/001_initial_schema.sql`
4. Click "Run"

---

## 🔍 Verificación Post-Instalación

```bash
# 1. Verificar tabla creada
SELECT * FROM public.v_documentos_stats;

# 2. Verificar función disponible
SELECT * FROM pg_proc WHERE proname = 'match_documentos';

# 3. Verificar extensiones
SELECT extname FROM pg_extension;

# 4. Probar búsqueda (si hay documentos)
SELECT * FROM match_documentos(
    query_embedding => CAST('[0.1, 0.2, ... (768 valores)]' AS vector),
    match_threshold => 0.7,
    match_count => 3
) LIMIT 3;
```

---

## 🎯 Decisiones de Diseño

| Decisión | Razón | Trade-off |
|----------|-------|-----------|
| **pgvector IVFFLAT** | Rápido para búsquedas aproximadas | Menos preciso que HNSW |
| **768 dimensiones** | Google text-embedding-004 standard | Tamaño de vector fijo |
| **Similitud coseno** | Estándar para embeddings textuales | Sensible a magnitud |
| **Redis con TTL 7 días** | Balance entre persistencia y privacy | Datos se pierden después de 7 días |
| **Memory backend configurable** | Flexibilidad dev/prod | Complejidad adicional |
| **Chunks con overlap=50** | Evita pérdida de contexto en límites | Aumenta datos almacenados |
| **ReAct con max 5 iteraciones** | Evita loops infinitos | Puede no resolver consultas complejas |

---

## 🛠️ Mantenimiento y Escalabilidad

### Limpieza de Documentos

```sql
-- Ver estadísticas por fuente
SELECT * FROM public.v_documentos_stats;

-- Eliminar documentos antiguos
DELETE FROM public.documentos 
WHERE created_at < NOW() - INTERVAL '1 year';

-- Eliminar por fuente específica
DELETE FROM public.documentos 
WHERE source = 'Documento Obsoleto';
```

### Optimización de Índices

```sql
-- Rebuild índice IVFFLAT después de muchos inserts
REINDEX INDEX idx_documentos_embedding_ivfflat;

-- Analizar tabla para actualizar estadísticas
ANALYZE public.documentos;
```

### Monitoreo

```sql
-- Size de tabla
SELECT 
    pg_size_pretty(pg_total_relation_size('public.documentos')) as size;

-- Cantidad de documentos por fuente
SELECT * FROM public.v_documentos_timeline;

-- Documentos sin embedding (error de ingestión)
SELECT * FROM public.documentos WHERE embedding IS NULL;
```

---

## 📚 Referencias Útiles

- **Supabase pgvector**: https://supabase.com/docs/guides/database/extensions/pgvector
- **Groq Embeddings**: https://groq.ai
- **Similitud Coseno**: https://en.wikipedia.org/wiki/Cosine_similarity
- **RLS en Supabase**: https://supabase.com/docs/guides/auth/row-level-security
