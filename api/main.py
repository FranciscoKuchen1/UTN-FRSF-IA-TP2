from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent.core import ReActAgent

app = FastAPI(title="Agente Estudio Contable", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev
    allow_methods=["*"],
    allow_headers=["*"]
)

# Cache simple de agentes por sesión (en producción: Redis)
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
        raise HTTPException(status_code=500, detail=str(e))
    
    return ChatResponse(response=response, session_id=req.session_id)

@app.delete("/chat/{session_id}")
async def clear_session(session_id: str):
    if session_id in _agents:
        del _agents[session_id]
    return {"cleared": True}

@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.2.0"}
