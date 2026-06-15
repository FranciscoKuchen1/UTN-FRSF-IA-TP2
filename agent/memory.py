import json
import redis
import os
from typing import Optional


class ShortTermMemory:
    """Historial de la sesión activa. Se incluye completo en cada llamada al LLM."""
    
    def __init__(self):
        self.messages: list[dict] = []
    
    def add(self, role: str, content: str):
        """role: 'user' | 'assistant' | 'tool'"""
        self.messages.append({"role": role, "content": content})
    
    def get_history(self) -> list[dict]:
        return self.messages.copy()
    
    def clear(self):
        self.messages = []

class LongTermMemory:
    """Persiste el perfil básico del cliente entre sesiones."""
    
    def __init__(self):
        self._redis = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
    
    def guardar_perfil(self, cliente_id: str, datos: dict):
        key = f"perfil:{cliente_id}"
        self._redis.setex(key, 86400 * 7, json.dumps(datos))  # TTL: 7 días
    
    def obtener_perfil(self, cliente_id: str) -> Optional[dict]:
        key = f"perfil:{cliente_id}"
        raw = self._redis.get(key)
        return json.loads(raw) if raw else None
    
    def actualizar_tipo_contribuyente(self, cliente_id: str, tipo: str):
        perfil = self.obtener_perfil(cliente_id) or {}
        perfil["tipo_contribuyente"] = tipo
        self.guardar_perfil(cliente_id, perfil)
