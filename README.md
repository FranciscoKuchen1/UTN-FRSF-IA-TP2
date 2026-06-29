# UTN-FRSF-IA-TP2 — Agente Asistente para Clientes de Estudio Contable

Agente conversacional (arquitectura **ReAct**) que responde consultas fiscales frecuentes
de clientes de un estudio contable, usando **RAG** sobre documentación interna, **tools**
funcionales y **memoria** conversacional. Ver el informe técnico de la 1ª entrega para el
detalle conceptual completo (objetivo, percepciones/acciones, ambiente y arquitectura).

Stack:
- **Backend**: Python + FastAPI, agente ReAct sobre Groq
- **RAG**: Supabase pgvector + Groq embeddings
- **Memoria**: corto plazo en context window; largo plazo (perfil del cliente) en **Redis Cloud** o en memoria de proceso
- **Frontend**: React + Vite + Tailwind CSS
- **Observabilidad**: Langfuse (opcional)

> Este proyecto **no requiere Docker ni infraestructura local compleja**. Se ejecuta backend
> y frontend directamente con Python y Node. Para memoria persistente, usa un Redis gratuito
> en la nube (Upstash o Redis Cloud) — ver instrucciones abajo.

---

## Requisitos previos

- Python 3.11+
- Node.js 18+ y npm
- Una API key de Groq
- **(Opcional)** Una database en Redis Cloud para persistencia (Upstash o Redis Cloud — ambas free)

---

## Quick Start (3 minutos)

### 1. Descargar y preparar

```bash
unzip UTN-FRSF-IA-TP2.zip
cd UTN-FRSF-IA-TP2

cp .env.example .env
```

### 2. Completar `.env`

Edita `.env` y completa **como mínimo**:

```env
GROQ_API_KEY=tu_api_key_aqui
LLM_MODEL=qwen/qwen3-32b
MEMORY_BACKEND=memory
```

> Para **producción / coloquio**, reemplaza `memory` con `redis` y agrega una URL de Redis Cloud
> (ver sección "Redis Cloud Setup" abajo).

### 3. Backend (Terminal 1)

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

uvicorn api.main:app --reload --port 8000
```

### 4. Frontend (Terminal 2)

```bash
cd frontend
npm install
npm run dev
```

Abre **http://localhost:5173** en tu navegador. ✓ Listo.

---

## Configuración de memoria: "memory" vs "redis"

### Para desarrollo rápido: `MEMORY_BACKEND=memory`

```env
MEMORY_BACKEND=memory
```

- ✓ Sin instalar nada (ni Redis local)
- ✓ Perfecto para testing y debugging local
- ✗ Se pierde el perfil del cliente al reiniciar el backend
- ✗ No apto para producción ni demos con múltiples sesiones

### Para coloquio / demostración: `MEMORY_BACKEND=redis` + Redis Cloud

```env
MEMORY_BACKEND=redis
REDIS_URL=rediss://default:password@host:port
```

- ✓ Persistencia: el perfil del cliente se mantiene entre reinicios
- ✓ Free tier generoso (Upstash: 10,000 comandos/día; Redis Cloud: similar)
- ✓ Sin gestionar servidores
- ✓ Listo para producción

**Ver instrucciones detalladas en `README-REDIS-CLOUD.md`** (en la raíz del proyecto).

---

## Redis Cloud Setup (recomendado)

### Opción A: Upstash (más simple)

1. Abre [https://console.upstash.com](https://console.upstash.com)
2. Crea una cuenta y verifica email
3. **Create Database** → selecciona región cercana (Sudamérica: São Paulo)
4. Copia **Redis URL** (empieza con `rediss://`)
5. En `.env`:
   ```env
   MEMORY_BACKEND=redis
   REDIS_URL=rediss://default:tu_password@tu-host.upstash.io:...
   ```

### Opción B: Redis Cloud (redis.com)

1. Abre [https://app.redis.com/](https://app.redis.com/)
2. Crea una cuenta y verifica email
3. **Create Database** → Free tier → selecciona región
4. Copia **Public Redis URL**
5. En `.env`:
   ```env
   MEMORY_BACKEND=redis
   REDIS_URL=rediss://default:tu_password@tu-host.cloud.redis.com:...
   ```

### Verificar conexión

```bash
python test_redis_connection.py
```

Deberías ver:
```
[OK] Conexión exitosa a Redis ✓
  - Redis version: 7.x
  - Memory used: xxx KB
  ...
```

Si hay error, lee `README-REDIS-CLOUD.md` para troubleshooting.

---

## Estructura del repositorio

```
agent/              lógica del agente ReAct
  ├── core.py       loop ReAct + llamada a LLM
  ├── memory.py     corto y largo plazo (aquí se configura Redis vs memory)
  ├── tools.py      herramientas del agente
  └── prompts.py    system prompt

api/                backend FastAPI
  └── main.py       endpoints (/chat, /health)

rag/                busqueda en documentos
  ├── retriever.py  búsqueda semántica en Supabase
  └── ingest.py     carga de PDFs

observability/      trazas a Langfuse (opcional)
  └── logger.py

frontend/           interfaz React + Tailwind
  ├── src/App.jsx   chat con sesiones
  └── ...

.env.example        variables de entorno (completar)
requirements.txt    dependencias Python
test_redis_connection.py  script para verificar Redis
README.md           esta guía
README-REDIS-CLOUD.md    instrucciones detalladas de Redis
```

---

## Levantar la aplicación paso a paso

### Terminal 1: Backend

```bash
# Desde la raíz del proyecto
python -m venv venv
source venv/bin/activate

pip install -r requirements.txt

# (Opcional) Verificar Redis si usas MEMORY_BACKEND=redis
python test_redis_connection.py

# Levantar servidor
uvicorn api.main:app --reload --port 8000
```

Verificar salud:
```bash
curl http://localhost:8000/health
# {"status":"ok","version":"0.3.0","memory_backend":"redis"}
```

### Terminal 2: Frontend

```bash
cd frontend
npm install
npm run dev

# Output:
#   ➜  Local: http://localhost:5173/
```

Abre en navegador → http://localhost:5173

### Terminal 3 (opcional): Monitoreo de Redis

Si usas Redis Cloud y quieres ver qué se guarda:

**Upstash**: Dashboard → tu database → pestaña "Data Browser"

**Redis Cloud**: Dashboard → tu database → pestaña "Data"

O con `redis-cli` (si tienes instalado):
```bash
redis-cli -u "rediss://default:password@host:port"
KEYS "perfil:*"
GET "perfil:web-abc123"
```

---

## Pruebas

Abre http://localhost:5173 e intenta preguntas:

- "¿Cuándo vence mi declaración de IVA este mes?"
- "¿Qué documentación necesito para ser responsable inscripto?"
- "En qué categoría de monotributo entro si facturo $15M al año?"

El agente razona, ejecuta tools, responde. Los logs aparecen en Terminal 1 (FastAPI).

Si usas `MEMORY_BACKEND=redis`, intenta:
1. Preguntar: "Soy monotributista"
2. Cerrar el navegador
3. Reabrir http://localhost:5173 (nueva pestaña)
4. El agente debería recordar: "Tipo de contribuyente del cliente: monotributo"

---

## Variables de entorno (`.env`)

| Variable | Requerida | Descripción |
|----------|-----------|-------------|
| `GROQ_API_KEY` | ✓ | API key de Groq |
| `MEMORY_BACKEND` | ✓ | `memory` (desarrollo) o `redis` (producción) |
| `REDIS_URL` | Si `MEMORY_BACKEND=redis` | URL de Redis Cloud (ej: `rediss://...`) |
| `SUPABASE_URL` | Si usas RAG | URL del proyecto Supabase |
| `SUPABASE_KEY` | Si usas RAG | Clave de Supabase |
| `NOMIC_API_KEY` | Para busqueda semantica | API key de Nomic; sin ella se usa busqueda textual |
| `ACCOUNTANT_WEBHOOK_URL` | Opcional | Webhook para notificar derivaciones; siempre queda una cola local |
| `LANGFUSE_SECRET_KEY` | Opcional | Clave de observabilidad |
| `LANGFUSE_PUBLIC_KEY` | Opcional | Clave de observabilidad |
| `MAX_REACT_ITERATIONS` | No (default: 5) | Máximo de pasos del agente |
| `FRONTEND_ORIGIN` | No (default: `http://localhost:5173`) | CORS origin |

---

## Troubleshooting

| Problema | Solución |
|----------|----------|
| `ModuleNotFoundError: No module named 'dotenv'` | Ejecuta `pip install -r requirements.txt` en venv activado |
| "No se pudo contactar al asistente" en el chat | ¿Corre FastAPI en Terminal 1? Verifica `http://localhost:8000/health` |
| Redis: "No se pudo conectar" | Ejecuta `python test_redis_connection.py`, revisa `README-REDIS-CLOUD.md` |
| El perfil del cliente no persiste | Verifica `MEMORY_BACKEND=redis` en `.env` y que `REDIS_URL` es correcta |
| `npm: command not found` | Instala Node.js desde https://nodejs.org/ |
| Port 8000 ya en uso | `uvicorn api.main:app --port 8001` (cambiar puerto) |

---

## Para la defensa del coloquio (29/06/2026)

Antes de presentar:

```bash
# Verificar que todo funciona
python test_redis_connection.py

# Levantar backend
uvicorn api.main:app --reload --port 8000

# Levantar frontend (otra terminal)
cd frontend && npm run dev
```

En vivo, muestra:
- Interfaz limpia y profesional (diseño tipo "expediente contable")
- Chat interactivo con preguntas típicas de clientes
- Logs del backend mostrando razonamiento del agente (ReAct)
- Persistencia: escribe un perfil, reinicia backend, el perfil se mantiene
- Escalado automático: pregunta fuera de dominio → se deriva al contador

---

## Siguiente paso: RAG en Supabase (opcional)

Si querés que el agente busque en documentos del estudio:

1. Crea un proyecto en [Supabase](https://supabase.com) (free)
2. Habilita `pgvector` en la BD
3. Completa `.env`:
   ```env
   SUPABASE_URL=https://...
   SUPABASE_KEY=...
   NOMIC_API_KEY=...  # necesario para generar embeddings al cargar archivos
   ```
4. Carga documentos:
   ```bash
   python -m rag.ingest --file docs/calendario.pdf --source "Calendario AFIP"
   python -m rag.ingest --file docs/guia.docx --source "Guia impositiva"
   python -m rag.ingest --file docs/notas.txt --source "Notas internas"
   ```

Ver `rag/ingest.py` para más detalles.

---

## Licencia

MIT. Ver `LICENSE.txt`.

---

## Contacto / Dudas

Cualquier error o duda sobre Redis Cloud, ver **`README-REDIS-CLOUD.md`** en la raíz del proyecto.
