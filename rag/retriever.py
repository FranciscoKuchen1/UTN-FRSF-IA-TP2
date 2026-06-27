import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

from supabase import create_client
from typing import Any

from rag.embeddings import embed_query

supabase = create_client(os.getenv("SUPABASE_URL", ""), os.getenv("SUPABASE_KEY", ""))

SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", 0.7))


def search_similar(query: str, top_k: int = 3) -> list[dict]:
    """Return the chunks most similar to the provided query from Supabase.

    Uses the `match_documentos` RPC on Supabase which expects a vector and
    returns rows with a `similarity` field.
    """
    query_embedding = embed_query(query)

    response = supabase.rpc(
        "match_documentos",
        {
            "query_embedding": query_embedding,
            "match_threshold": SIMILARITY_THRESHOLD,
            "match_count": top_k,
        },
    ).execute()

    # response.data can be a list or a single value; ensure we return a list
    data: Any = response.data
    if isinstance(data, list):
        return data
    elif data is None:
        return []
    else:
        return [data] if isinstance(data, dict) else []
