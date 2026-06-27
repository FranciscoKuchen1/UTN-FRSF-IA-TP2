import json
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)


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
    """
    Persiste el perfil básico del cliente entre sesiones.

    Backend configurable vía variable de entorno MEMORY_BACKEND:
      - "redis"  (default): requiere un servidor Redis accesible.
                  Puede ser local o un servicio en la nube (Upstash, Redis Cloud, etc.)
      - "memory": guarda todo en un diccionario en RAM del proceso.
                  Sirve para desarrollo local sin instalar/levantar nada.
                  ADVERTENCIA: se pierde el perfil del cliente si el backend se reinicia,
                  y no es apto para producción.

    Para usar Redis Cloud (recomendado para producción):
      1. Crea una cuenta en https://upstash.com/ o https://redis.com/cloud
      2. Crea un base de datos Redis (free tier disponible)
      3. Copia la URL de conexión (ej: rediss://default:password@host:port)
      4. Completa en .env: REDIS_URL=rediss://default:password@host:port
      5. Listo — sin cambios de código necesarios.
    """

    def __init__(self):
        self.backend = os.getenv("MEMORY_BACKEND", "redis").lower()

        if self.backend == "redis":
            import redis

            redis_url = os.getenv("REDIS_URL")
            if not redis_url:
                raise ValueError(
                    "MEMORY_BACKEND=redis pero REDIS_URL no está definida. "
                    "Completá .env con:\n"
                    "  REDIS_URL=redis://localhost:6379  (local)\n"
                    "  REDIS_URL=rediss://default:password@host:port  (Redis Cloud / Upstash)"
                )

            # redis-py maneja automáticamente:
            # - redis://  para conexiones sin SSL
            # - rediss:// para conexiones SSL (estándar en servicios cloud)
            # - Parsing de usuario/contraseña en la URL
            self._redis = redis.from_url(redis_url, decode_responses=True)

            # Verificar que la conexión funciona
            try:
                self._redis.ping()
            except Exception as e:
                raise RuntimeError(
                    f"No se pudo conectar a Redis en {redis_url}. "
                    f"Verificá que la URL es correcta. Error: {e}"
                )

        elif self.backend == "memory":
            self._store: dict[str, dict] = {}
        else:
            raise ValueError(f"MEMORY_BACKEND desconocido: '{self.backend}'. Usar 'redis' o 'memory'.")

    def guardar_perfil(self, cliente_id: str, datos: dict):
        """Guarda el perfil del cliente con TTL de 7 días."""
        if self.backend == "redis":
            key = f"perfil:{cliente_id}"
            self._redis.setex(key, 86400 * 7, json.dumps(datos))  # TTL: 7 días
        else:
            self._store[cliente_id] = datos

    def obtener_perfil(self, cliente_id: str) -> Optional[dict]:
        """Recupera el perfil del cliente si existe."""
        if self.backend == "redis":
            key = f"perfil:{cliente_id}"
            raw = self._redis.get(key)
            return json.loads(raw) if raw else None
        else:
            return self._store.get(cliente_id)

    def actualizar_tipo_contribuyente(self, cliente_id: str, tipo: str):
        """Actualiza el tipo de contribuyente en el perfil del cliente."""
        perfil = self.obtener_perfil(cliente_id) or {}
        perfil["tipo_contribuyente"] = tipo
        self.guardar_perfil(cliente_id, perfil)
