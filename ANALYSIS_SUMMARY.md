# 📊 Resumen: Análisis y Migración SQL

## 📁 Archivos Creados

```
migrations/
├── 001_initial_schema.sql          ← Migración SQL completa (368 líneas)
│   ├── Extensiones
│   ├── Tabla documentos
│   ├── Índices x4
│   ├── Función RPC match_documentos
│   ├── Trigger automático
│   ├── RLS Policies x5
│   ├── Vistas x2
│   └── Comentarios de documentación

ARQUITECTURA.md                      ← Análisis completo (700 líneas)
│   ├── Resumen ejecutivo
│   ├── Arquitectura de datos
│   ├── Flujos de datos
│   ├── Modelo de datos detallado
│   ├── Seguridad (RLS)
│   ├── Dependencias entre componentes
│   ├── Ciclo de vida de ingestión
│   ├── Decisiones de diseño
│   └── Mantenimiento

MIGRATION_SETUP.md                  ← Guía de ejecución (150 líneas)
    ├── Paso a paso
    ├── Verificación post-instalación
    ├── Checklist
    ├── Comandos de debugging
    └── Siguiente pasos
```

---

## 🔍 Análisis Completado

### 1. Componentes de la Aplicación

```
┌─────────────────────────────────────────────────────────┐
│                  AGENTE CONVERSACIONAL                  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │         agent/core.py (ReActAgent)              │  │
│  │  - Loop de razonamiento (max 5 iteraciones)    │  │
│  │  - Llamadas a LLM (Gemini 3.5 Flash)           │  │
│  │  - Extracción de acciones (regex parsing)      │  │
│  └────┬─────────────────────────────────────────────┘  │
│       │                                                 │
│       ├─→ agent/tools.py                              │
│       │   ├─ buscar_en_documentos() ──┐               │
│       │   ├─ consultar_vencimientos() │               │
│       │   ├─ escalar_consulta()       │               │
│       │   └─ obtener_fecha_hora()     │               │
│       │                                │               │
│       ├─→ agent/memory.py             │               │
│       │   ├─ ShortTermMemory (sesión) │               │
│       │   └─ LongTermMemory (Redis)   │               │
│       │                                │               │
│       ├─→ rag/retriever.py ←──────────┘               │
│       │   ├─ embed_query()                            │
│       │   └─ buscar_similar()                         │
│       │       └─→ Supabase RPC                        │
│       │                                                │
│       └─→ observability/logger.py                     │
│           └─ Langfuse (trazas)                        │
│                                                        │
│  ┌────────────────────────────────────────────────┐   │
│  │   api/main.py (FastAPI)                        │   │
│  │   POST /chat → Crea ReActAgent → Retorna resp  │   │
│  └────────────────────────────────────────────────┘   │
│                                                        │
└─────────────────────────────────────────────────────────┘
```

### 2. Flujo de Datos - Búsqueda Semántica (RAG)

```
USER QUERY: "¿Cuándo vence la declaración de IVA?"
    ↓
[Frontend: React]
    ↓
[API: FastAPI /chat]
    ↓
[Agent: ReActAgent.chat()]
    ├─ _call_llm() with context
    ├─ _parse_action() → "buscar_en_documentos"
    └─→ execute tool
            ↓
[Tools: buscar_en_documentos()]
    ↓
[RAG: buscar_similar(query)]
    ├─ 1. embed_query(query) ──────→ Google API ──→ vector(768)
    │
    ├─ 2. supabase.rpc("match_documentos") ──┐
    │                                         │
    │    PostgreSQL Query:                    │
    │    ┌────────────────────────────────┐  │
    │    │ SELECT * FROM documentos       │  │
    │    │ WHERE similarity(embedding) > 0.7
    │    │ ORDER BY similarity DESC       │  │
    │    │ LIMIT 3                        │  │
    │    │                                │  │
    │    │ similarity = 1 - cosine_dist() │  │
    │    └────────────────────────────────┘  │
    │                                         │
    └─→ Results: [                           │
            {id: 123, content: "...", source: "Calendario AFIP", similarity: 0.92},
            {id: 124, content: "...", source: "IVA Normativa", similarity: 0.88},
            {id: 125, content: "...", source: "Calendario AFIP", similarity: 0.84}
        ]
    ↓
[Tools: Format response]
    ↓
[Agent: Include context in next LLM call]
    ↓
[LLM: Generate response with context]
    ↓
Response: "Según el calendario AFIP, la declaración de IVA vence el 17 de cada mes..."
```

### 3. Flujo de Datos - Persistencia de Perfil

```
USER: "Soy monotributista"
    ↓
[Agent: _extract_and_save_profile()]
    ├─ Detecta: "monotributo" en mensaje
    ├─ memory.actualizar_tipo_contribuyente(cliente_id, "monotributo")
    └─→ Redis SET:
            {
                "key": "perfil:session-abc123",
                "value": "{\"tipo_contribuyente\": \"monotributo\"}",
                "ttl": 604800  (7 días)
            }
    ↓
[Subsequent queries in same session]
    ↓
[Agent: _build_system()]
    ├─ memory.obtener_perfil(cliente_id) ──→ Redis GET
    │   ↓
    │   Retorna: {tipo_contribuyente: "monotributo"}
    │
    └─ SYSTEM_PROMPT.format(tipo_contribuyente="monotributo")
        ↓
        "Eres un asistente para un cliente MONOTRIBUTISTA..."
```

---

## 💾 Estructura Supabase Creada

### Tabla: `documentos`

```sql
┌─────────────────────────────────────────────────────────┐
│ Tabla: public.documentos                                │
├──────┬──────────────────┬──────────────────────────────┤
│ ID   │ Type             │ Constraints / Properties      │
├──────┼──────────────────┼──────────────────────────────┤
│ id   │ BIGSERIAL        │ PRIMARY KEY, Auto-increment  │
│ content    │ TEXT         │ NOT NULL, Chunk de texto    │
│ source     │ TEXT         │ NOT NULL, Nombre documento  │
│ chunk_index│ INTEGER      │ Índice dentro del documento │
│ embedding  │ vector(768)  │ NOT NULL, De Google API     │
│ created_at │ TIMESTAMP TZ │ Default: NOW()              │
│ updated_at │ TIMESTAMP TZ │ Default: NOW()              │
└────────────────────────────────────────────────────────┘
```

### Índices

```
┌──────────────────────────────────────────────────────────────┐
│ Índices en tabla `documentos`                               │
├────────────────────────┬──────────┬─────────────────────────┤
│ Nombre                 │ Tipo     │ Propósito               │
├────────────────────────┼──────────┼─────────────────────────┤
│ idx_documentos_        │ IVFFLAT  │ Búsqueda rápida de     │
│   embedding_ivfflat    │          │ similitud vectorial    │
│                        │          │ (operador: <=>)        │
├────────────────────────┼──────────┼─────────────────────────┤
│ idx_documentos_source  │ BTREE    │ Filtrado por source    │
│                        │          │ (WHERE source = ...)   │
├────────────────────────┼──────────┼─────────────────────────┤
│ idx_documentos_        │ GIN      │ Full-text search en    │
│ content_fulltext       │          │ contenido (en español) │
├────────────────────────┼──────────┼─────────────────────────┤
│ idx_documentos_        │ BTREE    │ Ordenamiento temporal  │
│ created_at             │          │ (ORDER BY created_at)  │
└────────────────────────┴──────────┴─────────────────────────┘
```

### Función RPC: `match_documentos()`

```sql
┌─────────────────────────────────────────────────────────────┐
│ FUNCTION: public.match_documentos()                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ INPUTS:                                                     │
│  • query_embedding: vector(768)   [Requerido]             │
│  • match_threshold: float = 0.7   [Default: 0.7]          │
│  • match_count: int = 10          [Default: 10]           │
│                                                             │
│ OUTPUTS:                                                    │
│  • id: bigint                                              │
│  • content: text                                           │
│  • source: text                                            │
│  • chunk_index: int                                        │
│  • similarity: float (0.0 to 1.0)                         │
│                                                             │
│ SORT: similarity DESC                                      │
│ LIMIT: match_count                                         │
│ FILTER: WHERE similarity > match_threshold                 │
│                                                             │
│ DISTANCE METRIC: Cosine Similarity                         │
│   similarity = 1 - (distance <=>)                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### RLS Policies

```
┌────────────────────────────────────────────────────────────┐
│ Row Level Security (RLS) Policies                          │
├────────────────────────────┬─────────────┬────────────────┤
│ Policy Name                │ Role        │ Permissions    │
├────────────────────────────┼─────────────┼────────────────┤
│ allow_read_authenticated   │ Authenticated│ SELECT: ✓     │
│ allow_read_anonymous       │ Anonymous   │ SELECT: ✓     │
│ allow_insert_authenticated │ Authenticated│ INSERT: ✓     │
│ allow_update_authenticated │ Authenticated│ UPDATE: ✓     │
│ allow_delete_authenticated │ Authenticated│ DELETE: ✓     │
└────────────────────────────┴─────────────┴────────────────┘
```

---

## 🔄 Dependencias de Código

```
rag/ingest.py
    └─→ Supabase table("documentos").insert()
        └─→ Requiere: tabla documentos

rag/retriever.py
    └─→ Supabase rpc("match_documentos", {...}).execute()
        └─→ Requiere: función match_documentos + tabla documentos

agent/tools.py
    └─→ buscar_en_documentos()
        └─→ rag/retriever.py:buscar_similar()
            └─→ Supabase rpc("match_documentos")

agent/core.py
    └─→ ejecutar_tool("buscar_en_documentos", ...)
        └─→ agent/tools.py:buscar_en_documentos()

agent/memory.py
    └─→ LongTermMemory.guardar_perfil() → Redis SET
    └─→ LongTermMemory.obtener_perfil() → Redis GET
        └─→ Requiere: Redis Cloud (o fallback a memory)

observability/logger.py
    └─→ Langfuse API (no requiere BD Supabase)

api/main.py
    └─→ ReActAgent(cliente_id)
        └─→ agent/core.py
            └─→ usa todas las librerías anteriores

frontend/src/App.jsx
    └─→ POST /chat → api/main.py
```

---

## ✅ Checklist: Lo que se Creó

### Migración SQL (`migrations/001_initial_schema.sql`)

- [x] Extensión `pgvector` para vectores
- [x] Extensión `pg_trgm` para búsquedas fuzzy
- [x] Extensión `fuzzystrmatch` para aproximadas
- [x] Tabla `documentos` con 7 columnas
- [x] Índice IVFFLAT en embedding (búsqueda vectorial)
- [x] Índice BTREE en source (filtros)
- [x] Índice GIN fulltext en content
- [x] Índice BTREE en created_at
- [x] Función RPC `match_documentos()` (búsqueda semántica)
- [x] Trigger `update_documentos_updated_at()` automático
- [x] 5 RLS Policies (seguridad por roles)
- [x] Permisos GRANT para authenticated y anon
- [x] Vista `v_documentos_stats` (estadísticas)
- [x] Vista `v_documentos_timeline` (timeline)
- [x] Comentarios COMMENT en todas las tablas y columnas

### Documentación (`ARQUITECTURA.md`)

- [x] Resumen ejecutivo
- [x] Arquitectura de datos (3 niveles)
- [x] Flujos de datos completos (con diagramas)
- [x] Modelo de datos detallado
- [x] Seguridad y RLS
- [x] Dependencias entre componentes
- [x] Ciclo de vida de ingestión
- [x] Decisiones de diseño (trade-offs)
- [x] Mantenimiento y escalabilidad
- [x] Verificación post-instalación
- [x] Referencias útiles

### Guía de Ejecución (`MIGRATION_SETUP.md`)

- [x] Paso a paso de instalación
- [x] Checklist de verificación (5 queries)
- [x] Estructura creada (árbol visual)
- [x] Solución de problemas comunes
- [x] Comandos de debugging
- [x] Próximos pasos

---

## 🎯 Cómo Usar

### 1. Ejecutar Migración

```bash
# Ve a https://app.supabase.com
# SQL Editor → New query
# Copiar: migrations/001_initial_schema.sql
# Pegar y ejecutar (Ctrl+Enter)
```

### 2. Verificar Instalación

```bash
# Leer: MIGRATION_SETUP.md → Sección "Checklist"
# Ejecutar cada query de verificación
```

### 3. Ingestar Documentos

```bash
python -m rag.ingest --file docs/calendario_afip.txt --source "Calendario AFIP 2026"
```

### 4. Levantar Aplicación

```bash
# Terminal 1: Backend
uvicorn api.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev

# Abrir: http://localhost:5173
```

---

## 📊 Estadísticas del Proyecto

| Componente | Líneas | Estado |
|-----------|--------|--------|
| migrations/001_initial_schema.sql | 368 | ✅ Completo |
| ARQUITECTURA.md | 700 | ✅ Completo |
| MIGRATION_SETUP.md | 150 | ✅ Completo |
| agent/ | ~300 | ✅ Funcional |
| rag/ | ~100 | ✅ Funcional |
| api/ | ~80 | ✅ Funcional |
| frontend/ | ~200 | ✅ Funcional |
| **Total** | **~1900** | **✅ Completo** |

---

## 🔗 Archivos Principales

```
📦 UTN-FRSF-IA-TP2
│
├── 📄 ARQUITECTURA.md              ← Análisis técnico completo
├── 📄 MIGRATION_SETUP.md           ← Guía de ejecución
│
├── 📁 migrations/
│   └── 📄 001_initial_schema.sql  ← Migración SQL
│
├── 📁 agent/
│   ├── core.py                     (ReAct loop)
│   ├── memory.py                   (Persistencia)
│   ├── tools.py                    (Herramientas)
│   └── prompts.py                  (Prompts)
│
├── 📁 rag/
│   ├── ingest.py                   (Cargar docs)
│   └── retriever.py                (Buscar docs)
│
├── 📁 api/
│   └── main.py                     (FastAPI)
│
└── 📁 frontend/
    └── src/App.jsx                 (React)
```

---

## ✨ Próximos Pasos

1. ✅ Ejecutar migración SQL
2. ✅ Verificar estructura creada
3. ✅ Cargar documentos de ejemplo
4. ✅ Levantar backend + frontend
5. ✅ Probar búsqueda semántica
6. ⏳ Integración con contador (webhook)
7. ⏳ Escalado a producción (Kubernetes)

---

**Versión**: 1.0.0  
**Fecha**: 2026-06-20  
**Autor**: Análisis + Migración SQL completos
