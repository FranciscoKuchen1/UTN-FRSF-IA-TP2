import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent.core import ReActAgent

app = FastAPI(title="Agente sEstudio Contable", version="0.3.0")

# Orígenes permitidos para el frontend React (Vite usa 5173, CRA usa 3000).
# Se puede sobreescribir con la variable de entorno FRONTEND_ORIGIN en .env
_frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[_frontend_origin, "http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# Cache simple de agentes por sesión (en producción: persistir en Redis/DB)
_agents: dict[str, ReActAgent] = {}


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    response: str
    session_id: str


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if req.session_id not in _agents:
        _agents[req.session_id] = ReActAgent(cliente_id=req.session_id)

    agent = _agents[req.session_id]

    try:
        response = agent.chat(req.message)
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[ERROR] Fallo en chat: {error_trace}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

    return ChatResponse(response=response, session_id=req.session_id)


@app.delete("/chat/{session_id}")
async def clear_session(session_id: str):
    if session_id in _agents:
        del _agents[session_id]
    return {"cleared": True}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "0.3.0",
        "memory_backend": os.getenv("MEMORY_BACKEND", "redis"),
    }
