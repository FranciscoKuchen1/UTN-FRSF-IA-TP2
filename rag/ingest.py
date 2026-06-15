"""
Script para cargar PDFs del estudio en Supabase pgvector.
Uso: python -m rag.ingest --file docs/calendario_afip.pdf
"""
import os
import argparse
from supabase import create_client
import google.generativeai as genai

# Configuración
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

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
    """Genera embedding con Google text-embedding-004."""
    result = genai.embed_content(
        model="models/text-embedding-004",
        content=text,
        task_type="retrieval_document"
    )
    return result['embedding']

def ingest_document(file_path: str, source_name: str):
    """Lee un PDF/TXT, lo chunkea, vectoriza e inserta en Supabase."""
    # Leer texto (simplificado; en producción usar PyPDF2 o pymupdf)
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
