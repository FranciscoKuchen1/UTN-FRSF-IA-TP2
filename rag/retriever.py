import os
import re
from typing import Any

from dotenv import load_dotenv
from supabase import Client, create_client

from rag.embeddings import embed_query

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"),
    override=True,
)

SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.5"))
_supabase: Client | None = None


def _get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        url = os.getenv("SUPABASE_URL", "").strip()
        key = os.getenv("SUPABASE_KEY", "").strip()
        if not url or not key:
            raise RuntimeError("SUPABASE_URL y SUPABASE_KEY deben estar configuradas.")
        _supabase = create_client(url, key)
    return _supabase


def search_by_keywords(query: str, top_k: int = 3) -> list[dict]:
    """Fallback retrieval through PostgreSQL full-text search."""
    cleaned_query = " | ".join(
        re.findall(r"[\wáéíóúüñ]+", query, re.IGNORECASE)
    ).strip()
    if not cleaned_query:
        return []

    response = (
        _get_supabase()
        .table("documentos")
        .select("content,source,chunk_index")
        .text_search(
            "content",
            cleaned_query,
            options={"config": "spanish", "type": "websearch"},
        )
        .execute()
    )
    data: Any = response.data
    rows = data if isinstance(data, list) else []
    return [dict(row, retrieval_method="full_text") for row in rows][:top_k]


def search_similar(query: str, top_k: int = 3) -> list[dict]:
    """Retrieve document chunks semantically, with a full-text fallback."""
    semantic_error: Exception | None = None
    try:
        query_embedding = embed_query(query)
        if not query_embedding:
            raise RuntimeError("El proveedor de embeddings no devolvio un vector.")

        response = _get_supabase().rpc(
            "match_documentos",
            {
                "query_embedding": query_embedding,
                "match_threshold": SIMILARITY_THRESHOLD,
                "match_count": top_k,
            },
        ).execute()

        data: Any = response.data
        if isinstance(data, list) and data:
            return [dict(row, retrieval_method="semantic") for row in data]
        if isinstance(data, dict):
            return [dict(data, retrieval_method="semantic")]
        semantic_error = RuntimeError("La busqueda semantica no encontro coincidencias.")
    except Exception as exc:
        semantic_error = exc

    try:
        return search_by_keywords(query, top_k=top_k)
    except Exception as keyword_error:
        raise RuntimeError(
            "No se pudo consultar la base documental mediante busqueda "
            f"semantica ({type(semantic_error).__name__}) ni textual "
            f"({type(keyword_error).__name__})."
        ) from keyword_error
