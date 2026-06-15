import os
import google.generativeai as genai
from supabase import create_client

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", 0.7))

def embed_query(query: str) -> list[float]:
    result = genai.embed_content(
        model="models/text-embedding-004",
        content=query,
        task_type="retrieval_query"
    )
    return result['embedding']

def buscar_similar(query: str, top_k: int = 3) -> list[dict]:
    """Busca los chunks más similares a la query en Supabase."""
    query_embedding = embed_query(query)
    
    # RPC function en Supabase (ver abajo)
    response = supabase.rpc(
        "match_documentos",
        {
            "query_embedding": query_embedding,
            "match_threshold": SIMILARITY_THRESHOLD,
            "match_count": top_k
        }
    ).execute()
    
    return response.data or []
