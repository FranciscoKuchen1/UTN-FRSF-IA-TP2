"""
python -m rag.ingest --file docs/calendario_afip.pdf --source "Calendario AFIP 2026"
"""
import os
import argparse
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

from supabase import create_client

from rag.embeddings import embed_text

supabase = create_client(os.getenv("SUPABASE_URL", ""), os.getenv("SUPABASE_KEY", ""))

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into chunks with overlap."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk:
            chunks.append(chunk)
    return chunks

def ingest_document(file_path: str, source_name: str):
    """Read a text file, chunk it, embed each chunk and insert into Supabase."""
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()

    chunks = chunk_text(text)
    print(f"[INGEST] {len(chunks)} chunks from '{source_name}'")

    for i, chunk in enumerate(chunks):
        embedding = embed_text(chunk)
        supabase.table("documentos").insert({
            "content": chunk,
            "source": source_name,
            "chunk_index": i,
            "embedding": embedding,
        }).execute()
        print(f"  [{i+1}/{len(chunks)}] inserted")

    print("[INGEST] Completed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="Path to file to ingest")
    parser.add_argument("--source", default=None, help="Source name (default: file basename)")
    args = parser.parse_args()
    ingest_document(args.file, args.source or os.path.basename(args.file))
