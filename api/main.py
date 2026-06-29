
"""
Backend FastAPI — Agente Contable IA
=====================================

Endpoints públicos
  POST /auth/login   → autentica con Supabase Auth y devuelve el JWT
  GET  /health       → chequeo de estado del servicio

Endpoints protegidos (requieren 'Authorization: Bearer <token>')
  POST /chat         → envía un mensaje al agente ReAct
  DELETE /chat       → limpia el historial de la sesión activa
"""

import os
import tempfile
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client, AuthApiError

from agent.core import ReActAgent
from api.schemas import ChatRequest, ChatResponse, LoginRequest, LoginResponse, EscalationResponse, EscalationReplyRequest, ContactSettings
from api.services.notifications import ConsoleNotificationService

# ─── Clientes globales ────────────────────────────────────────────────────────

_supabase: Client = create_client(
    supabase_url=os.getenv("SUPABASE_URL", ""),
    supabase_key=os.getenv("SUPABASE_KEY", ""),
)

notification_service = ConsoleNotificationService()

# ─── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Agente Contable IA",
    version="0.4.0",
    description="Asistente virtual para clientes de estudio contable — arquitectura ReAct + RAG",
)


_frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_frontend_origin, "http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache de agentes por sesión (user_id como clave)

_agents: dict[str, ReActAgent] = {}


def _load_taxpayer_type(user_id: str) -> str | None:
    """Load the fiscal category stored in the user's profile."""
    try:
        response = (
            _supabase.table("profiles")
            .select("tipo_contribuyente")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        if response.data:
            return response.data[0].get("tipo_contribuyente")
    except Exception as exc:
        print(f"[WARN] No se pudo cargar el tipo de contribuyente: {exc}")
    return None

# ─── Dependencia de autenticación ────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
):
    """
    Dependencia de FastAPI que valida el JWT de Supabase.

    Flujo:
      1. Extrae el token del header 'Authorization: Bearer <token>'
      2. Llama a supabase.auth.get_user(token) para validar contra Supabase Auth
         (Supabase verifica firma, expiración y revocación internamente)
      3. Retorna el objeto User si el token es válido
      4. Lanza HTTP 401 en cualquier caso de fallo

    No se usa PyJWT ni python-jose; toda la validación la hace Supabase.
    """
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Token de autenticación requerido.",
        )

    token = credentials.credentials
    try:
        result = _supabase.auth.get_user(token)
        if result is None or result.user is None:
            raise HTTPException(status_code=401, detail="Token inválido o expirado.")
        return result.user
    except AuthApiError:
        # AuthApiError cubre: token expirado, firma inválida, usuario inexistente
        raise HTTPException(status_code=401, detail="Token inválido o expirado.")
    except HTTPException:
        raise
    except Exception:
        # Nunca exponer detalles internos de Supabase al cliente
        raise HTTPException(status_code=401, detail="Error de autenticación.")


def get_user_supabase(token: str) -> Client:
    """Crea un cliente Supabase configurado con el JWT del usuario para respetar RLS."""
    client = create_client(
        supabase_url=os.getenv("SUPABASE_URL", ""),
        supabase_key=os.getenv("SUPABASE_KEY", ""),
    )
    client.postgrest.auth(token)
    return client


async def get_current_admin(
    current_user=Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)
):
    """Dependencia que asegura que el usuario sea administrador y retorna un cliente autenticado."""
    try:
        token = credentials.credentials
        user_client = get_user_supabase(token)
        profile_res = user_client.table("profiles").select("role").eq("id", current_user.id).execute()
        role = profile_res.data[0].get("role") if profile_res.data else "cliente"
        if role != "admin":
            raise HTTPException(status_code=403, detail="No tienes permisos para realizar esta acción.")
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail="Error verificando permisos.")
    return {"user": current_user, "token": token, "client": user_client}


# ─── Endpoints públicos ───────────────────────────────────────────────────────

@app.post("/auth/login", response_model=LoginResponse, tags=["Auth"])
async def login(body: LoginRequest):
    """
    Autentica un cliente con email y contraseña usando Supabase Auth.
    Devuelve el JWT (access_token) que debe enviarse en los endpoints protegidos.
    """
    try:
        result = _supabase.auth.sign_in_with_password({
            "email": body.email,
            "password": body.password,
        })
        session = result.session
        user = result.user

        if session is None or user is None:
            raise HTTPException(status_code=401, detail="Credenciales incorrectas.")

        # Obtener el rol y nombre desde la tabla profiles
        role = "cliente"
        name = user.email.split("@")[0] if user.email else "Usuario"
        try:
            print(f"Buscando perfil para user.id: {user.id}")
            profile_res = (
                _supabase.table("profiles")
                .select("role,tipo_contribuyente,nombre,apellido")
                .eq("id", user.id)
                .execute()
            )
            print(f"Respuesta Supabase perfiles: {profile_res.data}")
            if profile_res.data and len(profile_res.data) > 0:
                p_data = profile_res.data[0]
                role = p_data.get("role", "cliente")
                nombre = p_data.get("nombre", "")
                apellido = p_data.get("apellido", "")
                if nombre or apellido:
                    name = f"{nombre} {apellido}".strip()
                print(f"Rol asignado: {role}, Nombre: {name}")
            else:
                print("No se encontró el perfil en la tabla profiles. Usando defaults.")
        except Exception as e:
            print(f"Excepción al buscar perfil: {e}")
            pass  # Si el perfil no existe aún o hay un error, el default seguro es 'cliente'

        return LoginResponse(
            access_token=session.access_token,
            user_id=str(user.id),
            role=role,
            name=name,
        )

    except AuthApiError:
        # Credenciales incorrectas, usuario no confirmado, etc.
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos.")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Error interno al autenticar.")


@app.get("/health", tags=["Sistema"])
async def health():
    """Chequeo de estado del servicio. No requiere autenticación."""
    return {
        "status": "ok",
        "version": "0.4.0",
        "memory_backend": os.getenv("MEMORY_BACKEND", "redis"),
    }


# ─── Endpoints protegidos ─────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(
    body: ChatRequest,
    current_user=Depends(get_current_user),   # JWT validado
):
    """
    Envía un mensaje al agente ReAct.

    El 'session_id' ya no se recibe del cliente: se extrae del JWT validado,
    lo que garantiza que cada usuario solo accede a su propia sesión.
    """
    user_id = str(current_user.id)

    if user_id not in _agents:
        _agents[user_id] = ReActAgent(
            client_id=user_id,
            taxpayer_type=_load_taxpayer_type(user_id),
        )

    agent = _agents[user_id]

    try:
        response = agent.chat(body.message)
    except RuntimeError as e:
        # Errores conocidos del agente (cuota agotada, credenciales, etc.)
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Error interno del agente.")

    return ChatResponse(response=response, session_id=user_id)


@app.delete("/chat", tags=["Chat"])
async def clear_session(current_user=Depends(get_current_user)):
    """
    Limpia el historial de la sesión del usuario autenticado.
    El agente se elimina del cache; en la próxima llamada se crea uno nuevo.
    """
    user_id = str(current_user.id)
    if user_id in _agents:
        del _agents[user_id]
    return {"cleared": True, "session_id": user_id}


@app.post("/admin/upload", tags=["Admin"])
async def upload_document(
    file: UploadFile = File(...),
    admin_data=Depends(get_current_admin)
):
    """
    Sube un documento y lo procesa para el RAG.
    Requiere ser administrador.
    """
    import re
    raw_filename = Path(file.filename or "documento").name
    # Sanitizar: reemplaza caracteres no alfanuméricos (excepto punto y guion) por guiones bajos
    filename = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', raw_filename)
    filename = re.sub(r'_+', '_', filename).strip('_')
    if not filename:
        filename = "documento"
    
    extension = Path(filename).suffix.lower()
    if extension not in {".pdf", ".docx", ".txt"}:
        raise HTTPException(
            status_code=415,
            detail="Formato no soportado. Usa PDF, DOCX o TXT.",
        )

    max_upload_size = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50")) * 1024 * 1024
    contents = await file.read(max_upload_size + 1)
    if len(contents) > max_upload_size:
        raise HTTPException(status_code=413, detail="El archivo supera el tamano permitido.")

    temp_path = None
    try:
        from rag.ingest import ingest_document
        
        # Crear un archivo temporal
        fd, temp_path = tempfile.mkstemp(suffix=extension)
        with os.fdopen(fd, "wb") as temp_file:
            temp_file.write(contents)
            
        # Llamar al flujo de ingestión
        summary = ingest_document(temp_path, source_name=filename)
        
        # Subir a Supabase Storage
        content_type = "application/pdf"
        if extension == ".docx":
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif extension == ".txt":
            content_type = "text/plain"
            
        try:
            _supabase.storage.from_("knowledge_base").upload(
                file=contents,
                path=filename,
                file_options={"content-type": content_type, "upsert": "true"}
            )
        except Exception as e:
            # Opcional: Podríamos revertir la ingestión aquí, pero lo reportamos
            print(f"[WARN] Error al subir original a Storage: {e}")
            
        return {"status": "success", "filename": filename, **summary}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error al procesar el archivo: {exc}",
        )
    finally:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)


@app.get("/admin/documents", tags=["Admin"])
async def get_documents(admin_data=Depends(get_current_admin)):
    """Obtiene la lista de documentos en la base de conocimiento desde Storage."""
    try:
        res = _supabase.storage.from_("knowledge_base").list()
        # Filtramos posibles archivos ocultos o carpetas
        files = [f for f in res if f.get("name") and not f["name"].startswith(".empty")]
        return files
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo documentos: {str(e)}")


@app.delete("/admin/documents/{filename}", tags=["Admin"])
async def delete_document(filename: str, admin_data=Depends(get_current_admin)):
    """Elimina un documento de Storage y sus chunks de la base de datos."""
    try:
        # Eliminar de Storage
        _supabase.storage.from_("knowledge_base").remove([filename])
        
        # Eliminar de BD (limpiar chunks)
        _supabase.table("documentos").delete().eq("source", filename).execute()
        
        return {"status": "success", "message": f"{filename} eliminado."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error eliminando documento: {str(e)}")


@app.delete("/admin/documents", tags=["Admin"])
async def delete_all_documents(admin_data=Depends(get_current_admin)):
    """Elimina TODOS los documentos de Storage y sus chunks de la base de datos."""
    try:
        # Listar y eliminar todos los archivos de Storage
        res = _supabase.storage.from_("knowledge_base").list()
        files = [f["name"] for f in res if f.get("name") and not f["name"].startswith(".empty")]
        if files:
            _supabase.storage.from_("knowledge_base").remove(files)
        
        # Eliminar todos los registros de la base de datos documental
        _supabase.table("documentos").delete().neq("id", 0).execute()
        
        return {"status": "success", "message": "Todos los documentos han sido eliminados."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error eliminando documentos: {str(e)}")


@app.get("/admin/escalations", response_model=list[EscalationResponse], tags=["Admin"])
async def get_escalations(admin_data=Depends(get_current_admin)):
    """Obtiene la lista de tickets de derivación pendientes."""
    try:
        user_client = admin_data["client"]
        res = user_client.table("escalations").select("*").eq("status", "pending").order("created_at", desc=True).execute()
        
        data = res.data
        if not data:
            return []
            
        user_ids = list(set(d["user_id"] for d in data))
        profiles_res = _supabase.table("profiles").select("id, nombre, apellido").in_("id", user_ids).execute()
        profiles_map = {p["id"]: f"{p.get('nombre') or ''} {p.get('apellido') or ''}".strip() for p in profiles_res.data}
        
        for d in data:
            d["user_name"] = profiles_map.get(d["user_id"]) or "Usuario"
            
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo derivaciones: {str(e)}")


@app.post("/admin/escalations/{ticket_id}/reply", tags=["Admin"])
async def reply_escalation(
    ticket_id: str, 
    body: EscalationReplyRequest, 
    admin_data=Depends(get_current_admin)
):
    """Responde a un ticket de derivación y lo marca como resuelto."""
    try:
        user_client = admin_data["client"]
        # Obtener el user_id del ticket
        res = user_client.table("escalations").select("user_id").eq("id", ticket_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Ticket no encontrado")
        user_id = res.data[0]["user_id"]
        
        # Enviar notificación
        notification_service.send_response(user_id, body.message)
        
        # Actualizar ticket
        user_client.table("escalations").update({
            "status": "resolved",
            "resolved_at": datetime.now().isoformat()
        }).eq("id", ticket_id).execute()
        
        return {"status": "success", "message": "Respuesta enviada correctamente."}
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/settings/contact", tags=["Settings"])
async def get_contact_settings():
    """Obtiene la info de contacto del estudio."""
    try:
        res = _supabase.table("settings").select("value").eq("key", "contact_info").execute()
        if res.data:
            return {"contact_info": res.data[0]["value"]}
        return {"contact_info": ""}
    except Exception as e:
        return {"contact_info": ""}

@app.post("/admin/settings/contact", tags=["Admin"])
async def update_contact_settings(
    settings: ContactSettings,
    admin_data=Depends(get_current_admin)
):
    """Actualiza la información de contacto del estudio."""
    try:
        user_client = admin_data["client"]
        user_client.table("settings").upsert({
            "key": "contact_info",
            "value": settings.contact_info,
            "updated_at": datetime.now().isoformat()
        }).execute()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error actualizando settings: {str(e)}")
