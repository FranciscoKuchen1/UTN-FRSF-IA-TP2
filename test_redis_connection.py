#!/usr/bin/env python3
"""
Script para verificar la conexión a Redis antes de levantar la aplicación.
Uso: python test_redis_connection.py

Útil para debugging de URLs incorrectas o credenciales inválidas.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

def test_redis_connection():
    """Prueba la conexión a Redis según la configuración en .env"""
    
    memory_backend = os.getenv("MEMORY_BACKEND", "redis").lower()
    
    print(f"[INFO] MEMORY_BACKEND = {memory_backend}")
    
    if memory_backend == "memory":
        print("[OK] Usando memoria en proceso (no requiere conexión a Redis)")
        return True
    
    elif memory_backend == "redis":
        redis_url = os.getenv("REDIS_URL")
        
        if not redis_url:
            print("[ERROR] MEMORY_BACKEND=redis pero REDIS_URL no está definida en .env")
            print("")
            print("Opciones:")
            print("  1. Edita .env y completa REDIS_URL")
            print("  2. O cambia a MEMORY_BACKEND=memory para desarrollo local")
            return False
        
        print(f"[INFO] Intentando conectar a: {redis_url[:50]}...")
        
        try:
            import redis
            client = redis.from_url(redis_url, decode_responses=True)
            ping_response = client.ping()
            
            if ping_response:
                print("[OK] Conexión exitosa a Redis ✓")
                print("")
                print("Detalles de la conexión:")
                info = client.info()
                print(f"  - Redis version: {info.get('redis_version', '?')}")
                print(f"  - Memory used: {info.get('used_memory_human', '?')}")
                print(f"  - Connected clients: {info.get('connected_clients', '?')}")
                return True
        
        except redis.exceptions.ConnectionError as e:
            print(f"[ERROR] No se pudo conectar a Redis")
            print(f"  Razón: {e}")
            print("")
            print("Checklist:")
            print("  ✓ ¿La URL de Redis está completa y sin espacios?")
            print("  ✓ ¿Empieza con rediss:// (doble s para SSL)?")
            print("  ✓ ¿Los datos están correctos (user, password, host, port)?")
            print("  ✓ ¿Tu IP está autorizada en el firewall del servicio?")
            print("")
            print("Alternativa para desarrollo local:")
            print("  MEMORY_BACKEND=memory (no requiere Redis)")
            return False
        
        except ImportError:
            print("[ERROR] redis-py no está instalado")
            print("  Ejecuta: pip install redis")
            return False
        
        except Exception as e:
            print(f"[ERROR] Error inesperado: {e}")
            return False
    
    else:
        print(f"[ERROR] MEMORY_BACKEND inválido: {memory_backend}")
        print("  Usa: 'redis' o 'memory'")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Verificador de conexión a Redis")
    print("=" * 60)
    print("")
    
    success = test_redis_connection()
    
    print("")
    print("=" * 60)
    
    if success:
        print("[✓] Listo para levantar la aplicación")
        print("")
        print("  Terminal 1: uvicorn api.main:app --reload --port 8000")
        print("  Terminal 2: cd frontend && npm run dev")
        sys.exit(0)
    else:
        print("[✗] Corrige los errores arriba antes de continuar")
        sys.exit(1)
