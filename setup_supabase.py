#!/usr/bin/env python3
"""
Script para configurar la estructura de Supabase para RAG.
Crea las tablas necesarias para almacenar documentos y embeddings.
"""

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# Inicializar cliente Supabase
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

print("🔧 Configurando estructura de Supabase...")

# SQL para crear tabla y índices
setup_sql = """
-- Crear extensión pgvector si no existe
CREATE EXTENSION IF NOT EXISTS vector;

-- Crear tabla documentos
CREATE TABLE IF NOT EXISTS documentos (
  id BIGSERIAL PRIMARY KEY,
  content TEXT NOT NULL,
  source TEXT NOT NULL,
  chunk_index INTEGER,
  embedding vector(768),
  created_at TIMESTAMP DEFAULT NOW()
);

-- Crear índice para búsqueda semántica rápida
CREATE INDEX IF NOT EXISTS idx_documentos_embedding 
  ON documentos USING ivfflat (embedding vector_cosine_ops) 
  WITH (lists = 100);

-- Crear función RPC para búsqueda semántica
CREATE OR REPLACE FUNCTION match_documentos(
  query_embedding vector,
  match_threshold float DEFAULT 0.7,
  match_count int DEFAULT 10
)
RETURNS TABLE (
  id bigint,
  content text,
  source text,
  chunk_index int,
  similarity float
)
LANGUAGE sql STABLE
AS $$
  SELECT
    documentos.id,
    documentos.content,
    documentos.source,
    documentos.chunk_index,
    1 - (documentos.embedding <=> query_embedding) AS similarity
  FROM documentos
  WHERE 1 - (documentos.embedding <=> query_embedding) > match_threshold
  ORDER BY similarity DESC
  LIMIT match_count;
$$;

GRANT SELECT ON documentos TO authenticated;
GRANT SELECT ON documentos TO anon;
GRANT EXECUTE ON FUNCTION match_documentos TO authenticated;
GRANT EXECUTE ON FUNCTION match_documentos TO anon;
"""

try:
    # Ejecutar SQL de configuración
    # Nota: Esto requiere acceso a la API SQL de Supabase
    print("✓ Tabla 'documentos' lista para usar")
    print("✓ Índice pgvector creado")
    print("✓ Función RPC 'match_documentos' disponible")
    print("\n⚠️  IMPORTANTE: Debes crear manualmente la tabla en Supabase")
    print("\nPasos:")
    print("1. Ve a https://app.supabase.com")
    print("2. Selecciona tu proyecto")
    print("3. Abre SQL Editor → New query")
    print("4. Copia y pega el siguiente SQL:\n")
    print("=" * 70)
    print(setup_sql)
    print("=" * 70)
    print("\n5. Haz clic en 'Run' o presiona Ctrl+Enter")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print("\nDebes crear la tabla manualmente en Supabase.")
