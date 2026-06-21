# 🚀 Setup Rápido: Ejecutar Migración SQL

## Opción A: Con Supabase CLI (Recomendado) ⚡

Más rápido y moderno:

```bash
supabase push
```

Esto ejecuta automáticamente todas las migraciones en la carpeta `migrations/`.

---

## Opción B: Manual en Supabase Dashboard

### Paso 1: Acceder a Supabase

1. Ve a https://app.supabase.com
2. Inicia sesión con tu cuenta
3. Selecciona tu proyecto UTN-FRSF-IA-TP2

### Paso 2: Abrír SQL Editor

En el panel izquierdo:
```
SQL Editor
    → New query
```

### Paso 3: Copiar y Pegar la Migración

Copia el contenido completo de:
```
migrations/001_initial_schema.sql
```

Y pégalo en el SQL Editor de Supabase.

### Paso 4: Ejecutar

Presiona el botón **"Run"** (esquina superior derecha)

O usa: **Ctrl+Enter** (Windows/Linux) / **Cmd+Enter** (Mac)

### Paso 5: Verificar Éxito

Deberías ver el mensaje:
```
✓ Query executed successfully
```

## ✅ Checklist Post-Instalación

Ejecuta estos queries para verificar que todo se creó correctamente:

### 1. Verificar tabla `documentos`

```sql
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' AND table_name = 'documentos';
```

Deberías ver una fila con `documentos`.

### 2. Verificar función `match_documentos`

```sql
SELECT routine_name 
FROM information_schema.routines 
WHERE routine_schema = 'public' AND routine_name = 'match_documentos';
```

Deberías ver una fila con `match_documentos`.

### 3. Verificar extensión `pgvector`

```sql
SELECT extname FROM pg_extension WHERE extname = 'vector';
```

Deberías ver una fila con `vector`.

### 4. Verificar índices

```sql
SELECT indexname 
FROM pg_indexes 
WHERE schemaname = 'public' AND tablename = 'documentos'
ORDER BY indexname;
```

Deberías ver:
- `idx_documentos_content_fulltext`
- `idx_documentos_created_at`
- `idx_documentos_embedding_ivfflat`
- `idx_documentos_source`

### 5. Verificar RLS policies

```sql
SELECT * FROM pg_policies WHERE tablename = 'documentos';
```

Deberías ver 5 políticas.

---

## 🎯 Ahora Puedes:

### Cargar Documentos

```bash
python -m rag.ingest --file docs/calendario_afip.txt --source "Calendario AFIP 2026"
python -m rag.ingest --file docs/monotributo.txt --source "Régimen Monotributo"
python -m rag.ingest --file docs/iva.txt --source "Normativa IVA"
```

### Verificar que se cargaron

```sql
SELECT source, COUNT(*) as chunks 
FROM public.documentos 
GROUP BY source;
```

### Probar búsqueda semántica

```sql
-- Primero: generar embedding de prueba (requiere ejecutar en Python)
-- Luego: probar la función
SELECT * FROM match_documentos(
    query_embedding => '[0.1, 0.2, 0.3, ...]'::vector,  -- 768 valores
    match_threshold => 0.7,
    match_count => 3
) LIMIT 3;
```

### Ver estadísticas

```sql
SELECT * FROM public.v_documentos_stats;
```

---

## 🆘 Si Algo Falla

### Error: "permission denied for schema public"

**Causa**: Usuario sin permisos en Supabase
**Solución**: Usa el usuario `postgres` en Supabase Dashboard:
1. Settings → Database
2. Usa credenciales de `postgres`

### Error: "extension 'vector' does not exist"

**Causa**: pgvector no está habilitado en tu base de datos
**Solución**: Ejecuta primero:
```sql
CREATE EXTENSION vector;
```

### Error: "function match_documentos does not exist"

**Causa**: La función no se creó correctamente
**Solución**: Verifica que ejecutaste toda la migración sin errores

### Tabla `documentos` existe pero vacía

**Causa**: Normal si aún no ingestaste documentos
**Solución**: 
```bash
python -m rag.ingest --file docs/calendario_afip.txt --source "Prueba"
```

---

## 📋 Estructura Creada

```
public.documentos (tabla)
├── id (BIGSERIAL PK)
├── content (TEXT)
├── source (TEXT)
├── chunk_index (INTEGER)
├── embedding (vector(768))
├── created_at (TIMESTAMP)
└── updated_at (TIMESTAMP)

Índices:
├── idx_documentos_embedding_ivfflat
├── idx_documentos_source
├── idx_documentos_content_fulltext
└── idx_documentos_created_at

Función RPC:
└── match_documentos(query_embedding, match_threshold, match_count)

Trigger:
└── update_documentos_updated_at

RLS Policies (5):
├── allow_read_authenticated
├── allow_read_anonymous
├── allow_insert_authenticated
├── allow_update_authenticated
└── allow_delete_authenticated

Vistas (2):
├── v_documentos_stats
└── v_documentos_timeline
```

---

## 🔄 Siguiente Paso

Una vez confirmado que la estructura se creó:

1. **Ingestar documentos**:
   ```bash
   python -m rag.ingest --file docs/calendario_afip.txt --source "Calendario AFIP 2026"
   ```

2. **Levantar el backend**:
   ```bash
   uvicorn api.main:app --reload --port 8000
   ```

3. **Levantar el frontend**:
   ```bash
   cd frontend && npm run dev
   ```

4. **Probar en http://localhost:5173**

---

## 📚 Documentación Completa

Ver `ARQUITECTURA.md` para:
- Diagrama de flujo completo
- Modelo de datos detallado
- Decisiones de diseño
- Mantenimiento y escalabilidad
