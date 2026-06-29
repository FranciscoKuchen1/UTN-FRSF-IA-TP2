import json
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)


class ShortTermMemory:
    """Session history included in each LLM call."""

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
    """Persist a small client profile between sessions.

    Configurable backend via `MEMORY_BACKEND` env var:
      - "redis" (default): requires a Redis server (local or cloud).
      - "memory": in-memory dict for development (non-persistent).
    """

    def __init__(self):
        self.backend = os.getenv("MEMORY_BACKEND", "redis").lower()

        if self.backend == "redis":
            import redis

            redis_url = os.getenv("REDIS_URL")
            if not redis_url:
                raise ValueError(
                    "MEMORY_BACKEND=redis but REDIS_URL is not defined.\n"
                    "Set REDIS_URL in .env, e.g. redis://localhost:6379 or rediss://default:password@host:port"
                )

            self._redis = redis.from_url(redis_url, decode_responses=True)

            try:
                self._redis.ping()
            except Exception as e:
                raise RuntimeError(f"Could not connect to Redis at {redis_url}. Error: {e}")

        elif self.backend == "memory":
            self._store: dict[str, dict] = {}
        else:
            raise ValueError(f"Unknown MEMORY_BACKEND: '{self.backend}'. Use 'redis' or 'memory'.")

    def save_profile(self, client_id: str, data: dict):
        """Save a client profile with a 7-day TTL when using Redis."""
        if self.backend == "redis":
            key = f"profile:{client_id}"
            self._redis.setex(key, 86400 * 7, json.dumps(data))
        else:
            self._store[client_id] = data

    def get_profile(self, client_id: str) -> Optional[dict]:
        """Retrieve a client profile if it exists."""
        if self.backend == "redis":
            key = f"profile:{client_id}"
            raw = self._redis.get(key)
            return json.loads(raw) if raw else None
        else:
            return self._store.get(client_id)

    def update_taxpayer_type(self, client_id: str, taxpayer_type: str):
        """Update the taxpayer type in the stored client profile."""
        profile = self.get_profile(client_id) or {}
        profile["taxpayer_type"] = taxpayer_type
        self.save_profile(client_id, profile)
