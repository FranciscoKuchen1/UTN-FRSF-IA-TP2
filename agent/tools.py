import json
import os
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from observability.logger import log_tool_call
from rag.retriever import search_similar


TOOLS_SCHEMA = [
    {
        "name": "search_documents",
        "description": (
            "Buscar documentos internos del estudio (regulaciones, calendarios y guias). "
            "Devuelve fragmentos y sus fuentes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Consulta en lenguaje natural"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_due_dates",
        "description": (
            "Devolver obligaciones cuyo vencimiento ocurre en el mes calendario indicado."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "taxpayer_type": {
                    "type": "string",
                    "enum": [
                        "monotributo",
                        "responsable_inscripto",
                        "empleado_relacion_dependencia",
                    ],
                },
                "month": {
                    "type": "integer",
                    "description": "Mes calendario del vencimiento (1-12)",
                },
            },
            "required": ["taxpayer_type", "month"],
        },
    },
    {
        "name": "escalate_query",
        "description": (
            "Registrar la consulta para revision humana. Usar ante fallos sin alternativa, "
            "falta de informacion o necesidad de criterio profesional."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
                "client_data": {"type": "string"},
            },
            "required": ["reason"],
        },
    },
    {
        "name": "get_current_datetime",
        "description": "Devolver la fecha y hora actual de Buenos Aires.",
        "parameters": {"type": "object", "properties": {}},
    },
]


def search_documents(query: str) -> dict:
    """Search the document index and preserve source metadata."""
    try:
        results = search_similar(query, top_k=3)
        if not results:
            return {
                "found": False,
                "message": "No se encontraron documentos relevantes para esta consulta.",
            }
        return {
            "found": True,
            "fragments": [
                {
                    "text": result.get("content", ""),
                    "source": result.get("source", "Fuente no informada"),
                    "chunk_index": result.get("chunk_index"),
                    "similarity": result.get("similarity"),
                    "retrieval_method": result.get("retrieval_method", "semantic"),
                }
                for result in results
            ],
        }
    except Exception as exc:
        return {
            "error": str(exc),
            "error_type": type(exc).__name__,
            "found": False,
        }


DUE_DATES = {
    "monotributo": {
        6: [
            {"obligation": "Pago mensual de monotributo", "due_date": "20/06/2026"},
            {"obligation": "Recategorizacion semestral", "due_date": "20/06/2026"},
        ],
        7: [{"obligation": "Pago mensual de monotributo", "due_date": "21/07/2026"}],
    },
    "responsable_inscripto": {
        6: [
            {"obligation": "Declaracion mensual de IVA", "due_date": "18/06/2026"},
            {"obligation": "Cuotas de impuesto a las ganancias", "due_date": "13/06/2026"},
        ],
        7: [{"obligation": "Declaracion mensual de IVA", "due_date": "17/07/2026"}],
    },
}


def get_due_dates(taxpayer_type: str, month: int) -> dict:
    if not isinstance(month, int) or not 1 <= month <= 12:
        return {"error": "El mes debe ser un numero entero entre 1 y 12."}

    dates = DUE_DATES.get(taxpayer_type, {}).get(month, [])
    if not dates:
        return {
            "taxpayer_type": taxpayer_type,
            "month": month,
            "due_dates": [],
            "note": "No hay vencimientos registrados para este periodo.",
        }
    return {"taxpayer_type": taxpayer_type, "month": month, "due_dates": dates}


def _write_escalation_queue(payload: dict) -> bool:
    configured_path = os.getenv("ESCALATION_LOG_PATH", "").strip()
    queue_path = Path(configured_path) if configured_path else (
        Path(__file__).resolve().parents[1] / "data" / "escalations.jsonl"
    )
    try:
        queue_path.parent.mkdir(parents=True, exist_ok=True)
        with queue_path.open("a", encoding="utf-8") as queue_file:
            queue_file.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return True
    except OSError as exc:
        print(f"[ESCALATION] Local queue write failed: {exc}")
        return False


def escalate_query(reason: str, client_data: str = "", context: dict | None = None) -> dict:
    """Persiste la consulta en la BD con un resumen generado por el LLM."""
    history = context.get("history", []) if context else []
    client_id = context.get("client_id", "anonymous") if context else "anonymous"
    llm_callable = context.get("llm_callable") if context else None
    
    summary = "Sin resumen disponible."
    if history and llm_callable:
        summary_prompt = (
            "Genera un breve resumen en ESPAÑOL (1 o 2 oraciones) del problema que el usuario "
            "esta intentando resolver, basandote exclusivamente en este historial:\n"
        )
        for msg in history:
            summary_prompt += f"{msg['role']}: {msg['content']}\n"
        
        try:
            raw_summary = llm_callable([{"role": "user", "content": summary_prompt}]).strip()
            summary = re.sub(r'<think>.*?</think>', '', raw_summary, flags=re.DOTALL).strip()
        except Exception as e:
            print(f"[ESCALATION] Error generando resumen: {e}")
            summary = "Error al generar resumen."

    # Extraer el último mensaje real del usuario
    user_msgs = [m.get("content", "") for m in history if m.get("role") == "user"]
    real_query = user_msgs[-1] if user_msgs else (client_data or reason)

    # Insertar en Supabase y obtener contacto
    saved = False
    contact_info = ""
    try:
        from supabase import create_client
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if url and key:
            _supabase = create_client(url, key)
            
            # Guardar el ticket
            _supabase.table("escalations").insert({
                "user_id": client_id,
                "original_query": real_query,
                "summary": summary,
                "status": "pending"
            }).execute()
            saved = True
            
            # Obtener el contacto
            res = _supabase.table("settings").select("value").eq("key", "contact_info").execute()
            if res.data and res.data[0]["value"]:
                contact_info = res.data[0]["value"]
                
        else:
            print("[ESCALATION] No Supabase credentials.")
    except Exception as exc:
        print(f"[ESCALATION] Error guardando ticket o leyendo settings: {exc}")

    if saved:
        message = "Tu consulta fue derivada a un contador. Lo revisaremos a la brevedad."
        if contact_info:
            message += f" También puedes comunicarte directamente al: {contact_info}"
    else:
        message = "No pude registrar la derivación automáticamente. Por favor, comunícate con el estudio."

    return {
        "escalated": saved,
        "message": message,
    }


def get_current_datetime() -> dict:
    now = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires"))
    weekday_map = {
        "Monday": "lunes",
        "Tuesday": "martes",
        "Wednesday": "miercoles",
        "Thursday": "jueves",
        "Friday": "viernes",
        "Saturday": "sabado",
        "Sunday": "domingo",
    }
    return {
        "date": now.strftime("%d/%m/%Y"),
        "time": now.strftime("%H:%M"),
        "month": now.month,
        "weekday": weekday_map.get(now.strftime("%A"), now.strftime("%A")),
    }


TOOL_MAP = {
    "search_documents": search_documents,
    "get_due_dates": get_due_dates,
    "escalate_query": escalate_query,
    "get_current_datetime": get_current_datetime,
}


def execute_tool(name: str, params: dict, context: dict | None = None) -> str:
    if name not in TOOL_MAP:
        return json.dumps({"error": f"Herramienta desconocida: {name}"})
    func = TOOL_MAP[name]
    
    if name == "escalate_query":
        params["context"] = context
        
    try:
        result = func(**params)
    except TypeError as exc:
        result = {
            "error": f"Parametros invalidos para la herramienta '{name}'.",
            "detail": str(exc),
        }
    except Exception as exc:
        result = {
            "error": f"La herramienta '{name}' fallo.",
            "error_type": type(exc).__name__,
        }

    log_tool_call(tool_name=name, input=params, output=result)
    return json.dumps(result, ensure_ascii=False)
