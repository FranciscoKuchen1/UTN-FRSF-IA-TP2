import json
import os
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


def escalate_query(reason: str, client_data: str = "") -> dict:
    """Persist the query locally and notify the webhook when configured."""
    payload = {
        "timestamp": datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).isoformat(),
        "reason": reason,
        "client_data": client_data,
        "status": "pending",
    }
    queued_locally = _write_escalation_queue(payload)

    webhook_url = os.getenv("ACCOUNTANT_WEBHOOK_URL", "").strip()
    webhook_sent = False
    if webhook_url:
        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            webhook_sent = response.status_code < 400
        except requests.RequestException as exc:
            print(f"[ESCALATION] Webhook delivery failed: {exc}")
    else:
        print("[ESCALATION] ACCOUNTANT_WEBHOOK_URL not configured; queued locally only.")

    print(f"[ESCALATION] {payload}")
    if webhook_sent:
        message = "Tu consulta fue derivada al contador. Se comunicara con vos a la brevedad."
    elif queued_locally:
        message = "Tu consulta quedo registrada para revision del contador."
    else:
        message = (
            "No pude registrar la derivacion automaticamente. "
            "Por favor, comunicate con el estudio contable."
        )

    return {
        "escalated": webhook_sent or queued_locally,
        "webhook_sent": webhook_sent,
        "queued_locally": queued_locally,
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


def execute_tool(name: str, params: dict) -> str:
    if name not in TOOL_MAP:
        return json.dumps({"error": f"Tool '{name}' not found"})

    try:
        result = TOOL_MAP[name](**params)
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
