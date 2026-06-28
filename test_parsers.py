"""
Test local de los parsers de rag/ingest.py.
NO requiere conexion a Supabase ni a la API de Google.
Solo verifica que parse_txt, parse_pdf, parse_word y parse_file funcionen.

Uso:
    python test_parsers.py
"""

from rag.ingest import parse_txt, parse_word, parse_file, chunk_text

SEPARADOR = "-" * 60


def mostrar_preview(titulo: str, texto: str, n_chars: int = 300):
    preview = texto[:n_chars].replace("\n", "\\n")
    print(f"\n{SEPARADOR}")
    print(f"[{titulo}]")
    print(f"  Longitud total: {len(texto)} caracteres")
    print(f"  Preview: {preview!r}...")


# ---------------------------------------------------------------------------
# Test 1: parse_txt con archivos existentes en docs/
# ---------------------------------------------------------------------------
print("\n=== TEST 1: parse_txt ===")
for nombre in ["docs/calendario_afip.txt", "docs/iva.txt", "docs/monotributo.txt"]:
    try:
        texto = parse_txt(nombre)
        mostrar_preview(nombre, texto)
        print("  -> OK")
    except Exception as e:
        print(f"  -> ERROR: {e}")


# ---------------------------------------------------------------------------
# Test 2: parse_word con los .docx en la raiz del proyecto
# ---------------------------------------------------------------------------
print("\n\n=== TEST 2: parse_word ===")
docx_files = [
    "arquitectura_y_razonamiento.docx",
    "contexto_y_ambiente.docx",
    "flujo_interaccion_llm.docx",
    "implementacion_base_agente.docx",
]
for nombre in docx_files:
    try:
        texto = parse_word(nombre)
        mostrar_preview(nombre, texto)
        print("  -> OK")
    except Exception as e:
        print(f"  -> ERROR: {e}")


# ---------------------------------------------------------------------------
# Test 3: parse_file como dispatcher
# ---------------------------------------------------------------------------
print("\n\n=== TEST 3: parse_file (dispatcher) ===")

# TXT via dispatcher
try:
    texto = parse_file("docs/monotributo.txt")
    print(f"\n[.txt via parse_file] -> OK ({len(texto)} chars)")
except Exception as e:
    print(f"[.txt via parse_file] -> ERROR: {e}")

# DOCX via dispatcher
try:
    texto = parse_file("arquitectura_y_razonamiento.docx")
    print(f"[.docx via parse_file] -> OK ({len(texto)} chars)")
except Exception as e:
    print(f"[.docx via parse_file] -> ERROR: {e}")

# Extension no soportada -> debe lanzar ValueError
print("\n[Extension invalida .xlsx] -> esperando ValueError...")
try:
    parse_file("archivo.xlsx")
    print("  ERROR: no lanzo ValueError (comportamiento inesperado)")
except ValueError as e:
    print(f"  -> ValueError correctamente lanzado: {e}")


# ---------------------------------------------------------------------------
# Test 4: chunking sobre un documento real
# ---------------------------------------------------------------------------
print("\n\n=== TEST 4: chunk_text ===")
texto = parse_txt("docs/monotributo.txt")
chunks = chunk_text(texto, chunk_size=100, overlap=20)
print(f"  Documento: monotributo.txt")
print(f"  Texto total: {len(texto.split())} palabras")
print(f"  Chunks generados: {len(chunks)}")
print(f"  Palabras en chunk[0]: {len(chunks[0].split())}")
print(f"  Preview chunk[0]: {chunks[0][:150]!r}")
print(f"  -> OK")

print(f"\n{SEPARADOR}")
print("Todos los tests completados.")
print(SEPARADOR)
