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

from dotenv import load_dotenv
load_dotenv()

import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client, AuthApiError

from agent.core import ReActAgent
from api.schemas import LoginRequest, LoginResponse, ChatRequest, ChatResponse

# ─── Clientes globales ────────────────────────────────────────────────────────

_supabase: Client = create_client(
    os.getenv("SUPABASE_URL", ""),
    os.getenv("SUPABASE_KEY", ""),
)

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

        # Obtener el rol desde la tabla profiles
        role = "cliente"
        try:
            print(f"Buscando perfil para user.id: {user.id}")
            profile_res = _supabase.table("profiles").select("role").eq("id", user.id).execute()
            print(f"Respuesta Supabase perfiles: {profile_res.data}")
            if profile_res.data and len(profile_res.data) > 0:
                role = profile_res.data[0].get("role", "cliente")
                print(f"Rol asignado: {role}")
            else:
                print("No se encontró el perfil en la tabla profiles. Usando default: cliente.")
        except Exception as e:
            print(f"Excepción al buscar perfil: {e}")
            pass  # Si el perfil no existe aún o hay un error, el default seguro es 'cliente'

        return LoginResponse(
            access_token=session.access_token,
            user_id=str(user.id),
            role=role,
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
        _agents[user_id] = ReActAgent(cliente_id=user_id)

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
