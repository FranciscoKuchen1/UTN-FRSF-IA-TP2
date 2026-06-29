"""
Modelos Pydantic para los endpoints de la API.

Separados de main.py para mantener el archivo principal limpio
y facilitar la importación desde tests o clientes internos.
"""
from pydantic import BaseModel


# ─── Auth ────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    """Body del endpoint POST /auth/login."""
    email: str       # Supabase valida el formato del email en el servidor
    password: str


class LoginResponse(BaseModel):
    """Respuesta exitosa del endpoint POST /auth/login."""
    access_token: str   # JWT emitido por Supabase
    user_id: str        # UUID del usuario en Supabase Auth
    role: str           # 'admin' | 'cliente' — leído de app_metadata en Supabase
    name: str | None = None


# ─── Chat ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """
    Body del endpoint POST /chat.

    Nota: 'session_id' fue eliminado. La identidad del usuario se extrae
    directamente del JWT validado por la dependencia get_current_user,
    de modo que el cliente solo necesita enviar su mensaje.
<<<<<<< HEAD
    Se agregó 'conversation_id' opcional para agrupar en diferentes conversaciones.
    """
    message: str
    conversation_id: str | None = None
=======
    """
    message: str
>>>>>>> 107ecc32707a82ca6c1a173fa8592ab6633bbfb7


class ChatResponse(BaseModel):
    """Respuesta del endpoint POST /chat."""
    response: str
    session_id: str     # user_id del JWT; útil para que el frontend
                        # pueda correlacionar mensajes en logs/debug
<<<<<<< HEAD
    conversation_id: str | None = None
=======
>>>>>>> 107ecc32707a82ca6c1a173fa8592ab6633bbfb7


# ─── Escalations ─────────────────────────────────────────────────────────────

from datetime import datetime

class EscalationResponse(BaseModel):
    id: str
    user_id: str
    user_name: str | None = None
    original_query: str
    summary: str
    status: str
    created_at: datetime
    resolved_at: datetime | None = None

class EscalationReplyRequest(BaseModel):
    message: str

class ContactSettings(BaseModel):
    contact_info: str
