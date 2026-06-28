"""
Script para cargar documentos del estudio en Supabase pgvector.

Formatos soportados:
  - .txt  -> lectura directa con open()
  - .pdf  -> PyMuPDF (fitz)
  - .docx -> python-docx

Uso:
  python -m rag.ingest --file docs/calendario_afip.pdf --source "Calendario AFIP 2026"
  python -m rag.ingest --file docs/monotributo.docx   --source "Guia Monotributo"
  python -m rag.ingest --file docs/notas.txt          --source "Notas internas"
"""
import os
import re
import argparse
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

from supabase import create_client

from rag.embeddings import embed_text

supabase = create_client(os.getenv("SUPABASE_URL", ""), os.getenv("SUPABASE_KEY", ""))


# ---------------------------------------------------------------------------
# Parsers por formato
# ---------------------------------------------------------------------------

def parse_pdf(path: str) -> str:
    """
    Extrae texto de todas las paginas de un PDF usando PyMuPDF.
    Limpia espacios multiples, tabs y saltos de linea excesivos.
    """
    import fitz  # PyMuPDF

    doc = fitz.open(path)
    paginas = []
    for pagina in doc:
        texto = pagina.get_text("text")          # preserva orden de lectura
        texto = re.sub(r"[ \t]+", " ", texto)    # colapsar espacios/tabs multiples
        texto = re.sub(r"\n{3,}", "\n\n", texto) # maximo dos saltos consecutivos
        texto = "\n".join(line.strip() for line in texto.splitlines())
        paginas.append(texto.strip())
    doc.close()

    return "\n\n".join(p for p in paginas if p)


def parse_word(path: str) -> str:
    """
    Extrae texto de los parrafos de un archivo .docx usando python-docx.
    Ignora parrafos vacios para no introducir ruido en los chunks.
    """
    from docx import Document

    doc = Document(path)
    parrafos = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(parrafos)


def parse_txt(path: str) -> str:
    """Lee un archivo de texto plano en UTF-8."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def parse_file(path: str) -> str:
    """
    Detecta la extension del archivo y delega al parser correspondiente.

    Extensiones soportadas: .pdf, .docx, .txt
    Lanza ValueError si la extension no esta soportada.
    """
    ext = os.path.splitext(path)[1].lower()
    parsers = {
        ".pdf":  parse_pdf,
        ".docx": parse_word,
        ".txt":  parse_txt,
    }
    if ext not in parsers:
        raise ValueError(
            f"Extension '{ext}' no soportada. "
            f"Formatos validos: {', '.join(parsers)}"
        )
    return parsers[ext](path)


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into chunks with overlap."""
    words = text.split()
    chunks = []
    step = chunk_size - overlap
    for i in range(0, len(words), step):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk:
            chunks.append(chunk)
    return chunks


def ingest_document(file_path: str, source_name: str):
    """
    Orquesta el pipeline completo:
      1. Parsea el archivo (PDF / DOCX / TXT) con parse_file()
      2. Divide el texto en chunks con overlap
      3. Genera un embedding por chunk
      4. Inserta cada chunk + embedding + metadatos en Supabase
    """
    print(f"[INGEST] Parseando '{file_path}'...")
    text = parse_file(file_path)  # usa el dispatcher, no open() directo

    chunks = chunk_text(text)
    print(f"[INGEST] {len(chunks)} chunks generados de '{source_name}'")

    for i, chunk in enumerate(chunks):
        embedding = embed_text(chunk)
        supabase.table("documentos").insert({
            "content":     chunk,
            "source":      source_name,
            "chunk_index": i,
            "embedding": embedding,
        }).execute()
        print(f"  [{i+1}/{len(chunks)}] inserted")

    print("[INGEST] Completed.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Carga un documento (PDF/DOCX/TXT) en Supabase pgvector."
    )

    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="Path to file to ingest")
    parser.add_argument("--source", default=None, help="Source name (default: file basename)")

    args = parser.parse_args()

    ingest_document(args.file, args.source or os.path.basename(args.file))
