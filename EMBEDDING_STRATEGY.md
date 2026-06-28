# 📊 Estrategia de Embeddings: Análisis y Decisión

## 🔴 Problema Identificado

```
Google Gemini Embedding 2 genera:     3072 dimensiones
pgvector IVFFLAT permite máximo:      2000 dimensiones ❌
pgvector HNSW permite máximo:         2000 dimensiones ❌
```

**No hay índice vectorial nativo en PostgreSQL que soporte 3072 dimensiones.**

---

## 💭 Opciones Evaluadas

### Opción 1: Búsqueda Secuencial (Sin Índice) ✅ ELEGIDA
**Descripción**: Usar `vector(3072)` pero sin índice vectorial. Las búsquedas usan el operador `<=>` directamente.

**Ventajas**:
- ✅ Funciona correctamente con 3072 dimensiones
- ✅ Soporta precisión completa de Google embeddings
- ✅ No requiere cambios en la aplicación
- ✅ Sin transformación de datos

**Desventajas**:
- ⚠️ Búsqueda más lenta (secuencial, O(n) vs O(log n))
- ⚠️ Con millones de documentos, puede ser muy lento

**Cuándo es viable**:
- ✅ Desarrollo y pruebas (mejor para empezar)
- ✅ Hasta ~10,000-50,000 documentos
- ✅ Cuando la precisión es más importante que velocidad

---

### Opción 2: Reducir Dimensionalidad a 1500
**Descripción**: Usar PCA u otra técnica en la aplicación para reducir 3072 → 1500, luego usar HNSW.

**Ventajas**:
- ✅ Índice HNSW rápido (O(log n))
- ✅ Búsqueda muy rápida

**Desventajas**:
- ⚠️ Pierde 50% de información
- ⚠️ Requiere implementar PCA en `rag/ingest.py` y `rag/retriever.py`
- ⚠️ Necesita regenerar todos los embeddings existentes

**Cuándo usar**:
- Después de tener millones de documentos
- Cuando la velocidad es crítica

---

### Opción 3: Cambiar Modelo de Embedding
**Descripción**: Usar un modelo de embedding con menos dimensiones (ej: 384, 768).

**Problema**: 
- ❌ Google Gemini solo ofrece 3072 dimensiones
- ❌ Requeriría cambiar a otro proveedor (OpenAI, Cohere, etc.)

**No viable** con Google Gemini.

---

## ✅ Decisión: Opción 1 (Búsqueda Secuencial)

### Razones:
1. **Simplicidad**: Sin cambios en código
2. **Precisión**: Mantiene 3072 dimensiones completas
3. **Pragmatismo**: Funciona inmediatamente
4. **Escalabilidad**: Fácil de optimizar luego si es necesario

### Estructura Actual:
```sql
CREATE TABLE public.documentos (
    id BIGSERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    source TEXT NOT NULL,
    chunk_index INTEGER,
    embedding vector(3072) NOT NULL,  -- Sin índice vectorial
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Índices (no vectoriales):
CREATE INDEX idx_documentos_source ON public.documentos (source);
CREATE INDEX idx_documentos_content_fulltext ON public.documentos USING GIN (to_tsvector('spanish', content));
CREATE INDEX idx_documentos_created_at ON public.documentos (created_at DESC);

-- Búsqueda: secuencial con operador <=>
SELECT * FROM match_documentos(query_embedding, 0.7, 3)
-- Internamente: ... WHERE (1 - (embedding <=> query_embedding)) > 0.7 ...
```

---

## 📈 Plan de Escalamiento Futuro

### Si el sistema crece:

**Fase 1 (Actual)**: 
- Búsqueda secuencial, sin índice
- Viable hasta ~50k documentos
- Tiempo de búsqueda: ~100-500ms

**Fase 2 (Cuando sea necesario)**:
- Implementar PCA para reducir a 1500 dims
- Crear índice HNSW en 1500 dims
- Tiempo de búsqueda: ~10-50ms
- Requiere regenerar embeddings

**Fase 3 (Máxima escala)**:
- Usar búsqueda vectorial externa (Milvus, Weaviate, Pinecone)
- Mantener Supabase solo para metadata
- Tiempo de búsqueda: <10ms
- Costo: servicio vectorial adicional

---

## 🔧 Implementación Técnica

### In `rag/retriever.py`:
```python
def search_similar(query: str, top_k: int = 3) -> list[dict]:
    """Sequential search (no vector index)."""
    query_embedding = embed_query(query)  # 3072 dims

    # RPC call to Supabase
    response = supabase.rpc(
        "match_documentos",
        {
            "query_embedding": query_embedding,  # 3072 dims
            "match_threshold": 0.7,
            "match_count": top_k,
        },
    ).execute()

    return response.data
```

### En `migrations/001_initial_schema.sql`:
```sql
CREATE OR REPLACE FUNCTION match_documentos(
    query_embedding vector,
    match_threshold float DEFAULT 0.7,
    match_count int DEFAULT 10
)
RETURNS TABLE (...)
LANGUAGE sql STABLE SECURITY DEFINER
AS $$
    SELECT
        id, content, source, chunk_index,
        (1 - (embedding <=> query_embedding))::float AS similarity
    FROM documentos
    WHERE (1 - (embedding <=> query_embedding)) > match_threshold
    ORDER BY similarity DESC
    LIMIT match_count;
$$;
```

**Nota**: Sin índice, PostgreSQL hace secuencial scan. Funciona correctamente pero es O(n).

---

## 📊 Comparación: Rendimiento Estimado

| Métrica | Sin Índice (Actual) | Con HNSW (1500 dims) | Búsqueda Externa |
|---------|-------------------|-------------------|-----------------| 
| Documentos soportados | 50k-100k | 1M+ | Ilimitados |
| Tiempo búsqueda (10k docs) | 50-100ms | 5-10ms | 1-5ms |
| Precisión | 100% (3072 dims) | 98% (1500 dims) | 99%+ |
| Complejidad implementación | Baja ✅ | Media ⚠️ | Alta ❌ |
| Costo | $0 | $0 | $50-500/mes |

---

## 🎯 Conclusión

**Solución actual**: Búsqueda secuencial sin índice vectorial
- ✅ Funciona correctamente
- ✅ Mantiene precisión completa
- ✅ Fácil de implementar
- ✅ Escalable cuando sea necesario

**Cuándo optimizar**:
- Cuando haya >50k documentos y búsquedas sean lentas
- Cuando métricas indiquen cuellos de botella en similitud
- Como mejora de rendimiento, no como fix de funcionalidad

---

## 📝 Notas

- Cambios no requieren actualización de código Python
- Migraciones SQL están listas y probadas
- Sistema es fully funcional en producción con esta estrategia
- Optimizaciones futuras son backward-compatible
