import os
from dotenv import load_dotenv
load_dotenv()

from google import genai
from supabase import create_client
from typing import Any

supabase = create_client(os.getenv("SUPABASE_URL", ""), os.getenv("SUPABASE_KEY", ""))
genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", 0.7))

def embed_query(query: str) -> list[float]:
    result = genai_client.models.embed_content(
        model="models/gemini-embedding-2",
        contents=query
    )
    # result.embeddings es una lista de objetos Embedding, cada uno con .values
    if not result.embeddings:
        return []
    values = result.embeddings[0].values
    return values if values is not None else []

def buscar_similar(query: str, top_k: int = 3) -> list[dict]:
    """Busca los chunks más similares a la query en Supabase."""
    query_embedding = embed_query(query)

    response = supabase.rpc(
        "match_documentos",
        {
            "query_embedding": query_embedding,
            "match_threshold": SIMILARITY_THRESHOLD,
            "match_count": top_k
        }
    ).execute()

    # response.data puede ser una lista o un valor singular; asegurar que retornamos lista
    data: Any = response.data
    if isinstance(data, list):
        return data
    elif data is None:
        return []
    else:
        # Si es un dict singular, retornar en lista
        return [data] if isinstance(data, dict) else []
