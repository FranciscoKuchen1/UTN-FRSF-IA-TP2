import os
from typing import Any

from dotenv import load_dotenv

EMBEDDING_DIMENSION = 3072

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

try:
    from nomic import embed as nomic_embed
    from nomic import login as nomic_login
except ImportError:  # pragma: no cover - dependency may be absent in some environments
    nomic_embed = None
    nomic_login = None


def _normalize_model_name(model_name: str | None) -> str:
    if not model_name:
        return "nomic-embed-text-v1.5"

    model = model_name.strip()
    if model == "nomic-embed-text-v1_5":
        return "nomic-embed-text-v1.5"
    return model


def _get_embedding_model() -> str:
    return _normalize_model_name(
        os.getenv("NOMIC_EMBEDDING_MODEL")
        or os.getenv("GROQ_EMBEDDING_MODEL")
        or "nomic-embed-text-v1.5"
    )


def normalize_embedding(embedding: list[float], target_dim: int = EMBEDDING_DIMENSION) -> list[float]:
    """Ajusta un embedding al tamaño esperado por la tabla de Supabase."""
    if len(embedding) == target_dim:
        return embedding

    if len(embedding) > target_dim:
        return embedding[:target_dim]

    return embedding + [0.0] * (target_dim - len(embedding))


def _nomic_embed_text(texts: list[str], task_type: str = "search_document") -> dict[str, Any]:
    if nomic_embed is None:
        raise RuntimeError("La librería 'nomic' no está instalada.")

    api_key = (
        os.getenv("NOMIC_API_KEY")
        or os.getenv("NOMIC_API_TOKEN")
        or os.getenv("NOMIC_TOKEN")
    )
    if api_key and nomic_login is not None:
        try:
            nomic_login(api_key)
        except Exception:
            pass

    if not api_key:
        raise RuntimeError(
            "NOMIC_API_KEY no está configurado. Define el token en el .env o autentícate con `nomic login <token>` antes de ingerir documentos."
        )

    return nomic_embed.text(
        texts=texts,
        model=_get_embedding_model(),
        task_type=task_type,
        long_text_mode="truncate",
    )


def embed_text(text: str) -> list[float]:
    """Genera un embedding para un chunk de texto usando Nomic."""
    result = _nomic_embed_text([text], task_type="search_document")
    embeddings = result.get("embeddings") or []
    if not embeddings:
        return []
    return normalize_embedding(embeddings[0])


def embed_query(query: str) -> list[float]:
    """Genera un embedding para una query usando Nomic."""
    result = _nomic_embed_text([query], task_type="search_query")
    embeddings = result.get("embeddings") or []
    if not embeddings:
        return []
    return normalize_embedding(embeddings[0])
