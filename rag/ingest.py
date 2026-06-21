"""
Script para cargar PDFs del estudio en Supabase pgvector.
Uso: python -m rag.ingest --file docs/calendario_afip.pdf --source "Calendario AFIP 2026"
"""
import os
import argparse
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client
from google import genai

supabase = create_client(os.getenv("SUPABASE_URL", ""), os.getenv("SUPABASE_KEY", ""))
genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Divide el texto en chunks con overlap."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk:
            chunks.append(chunk)
    return chunks

def embed_text(text: str) -> list[float]:
    """Genera embedding con Google Gemini Embedding 2."""
    result = genai_client.models.embed_content(
        model="models/gemini-embedding-2",
        contents=text
    )
    # result.embeddings es una lista de objetos Embedding, cada uno con .values
    if not result.embeddings:
        return []
    values = result.embeddings[0].values
    return values if values is not None else []

def ingest_document(file_path: str, source_name: str):
    """Lee un PDF/TXT, lo chunkea, vectoriza e inserta en Supabase."""
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()

    chunks = chunk_text(text)
    print(f"[INGEST] {len(chunks)} chunks de '{source_name}'")

    for i, chunk in enumerate(chunks):
        embedding = embed_text(chunk)
        supabase.table("documentos").insert({
            "content": chunk,
            "source": source_name,
            "chunk_index": i,
            "embedding": embedding
        }).execute()
        print(f"  [{i+1}/{len(chunks)}] insertado")

    print("[INGEST] Completado.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="Ruta al archivo a ingerir")
    parser.add_argument("--source", default=None, help="Nombre de fuente (default: nombre del archivo)")
    args = parser.parse_args()
    ingest_document(args.file, args.source or os.path.basename(args.file))
