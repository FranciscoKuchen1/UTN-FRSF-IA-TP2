import json
import os
from datetime import datetime

import requests

from rag.retriever import search_similar
from observability.logger import log_tool_call


TOOLS_SCHEMA = [
    {
        "name": "search_documents",
        "description": "Buscar documentos internos del estudio (regulaciones, calendarios y guías de AFIP). Usar como primer recurso para consultas tributarias.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language query"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_due_dates",
        "description": "Devolver vencimientos para un tipo de contribuyente y un mes.",
        "parameters": {
            "type": "object",
            "properties": {
                "taxpayer_type": {"type": "string", "enum": ["monotributo", "responsable_inscripto", "empleado_relacion_dependencia"]},
                "month": {"type": "integer", "description": "Month number (1-12)"},
            },
            "required": ["taxpayer_type", "month"],
        },
    },
    {
        "name": "escalate_query",
        "description": "Registrar la consulta para revisión humana y notificar al contador. Usar cuando la pregunta está fuera de alcance.",
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
        "description": "Devolver la fecha y hora actuales (Buenos Aires). Usar para calcular vencimientos relativos.",
        "parameters": {"type": "object", "properties": {}},
    },
]

def search_documents(query: str) -> dict:
    """RAG: semantic search in Supabase pgvector"""
    try:
        results = search_similar(query, top_k=3)
        if not results:
            return {"found": False, "message": "No se encontraron documentos relevantes para esta consulta."}
        return {
            "found": True,
            "fragments": [
                {"text": r["content"], "source": r["source"], "similarity": r["similarity"]}
                for r in results
            ],
        }
    except Exception as e:
        return {"error": str(e), "found": False}

DUE_DATES = {
    "monotributo": {
        6: [
            {"obligation": "Pago mensual de monotributo", "due_date": "20/06/2026"},
            {"obligation": "Recategorización semestral", "due_date": "20/06/2026"},
        ],
        7: [{"obligation": "Pago mensual de monotributo", "due_date": "21/07/2026"}],
    },
    "responsable_inscripto": {
        6: [
            {"obligation": "Declaración mensual de IVA", "due_date": "18/06/2026"},
            {"obligation": "Cuotas de impuesto a las ganancias", "due_date": "13/06/2026"},
        ],
        7: [{"obligation": "Declaración mensual de IVA", "due_date": "17/07/2026"}],
    },
}

def get_due_dates(taxpayer_type: str, month: int) -> dict:
    dates = DUE_DATES.get(taxpayer_type, {}).get(month, [])
    if not dates:
        return {"taxpayer_type": taxpayer_type, "month": month, "due_dates": [], "note": "No hay vencimientos registrados para este período."}
    return {"taxpayer_type": taxpayer_type, "month": month, "due_dates": dates}


def escalate_query(reason: str, client_data: str = "") -> dict:
    """Record the query and send it to the accountant webhook when configured."""
    payload = {
        "timestamp": datetime.now().isoformat(),
        "reason": reason,
        "client_data": client_data,
        "status": "pending",
    }

    webhook_url = os.getenv("ACCOUNTANT_WEBHOOK_URL", "").strip()
    webhook_sent = False

    if webhook_url:
        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            webhook_sent = response.status_code < 400
        except Exception as exc:
            print(f"[ESCALATION] Webhook delivery failed: {exc}")
    else:
        print("[ESCALATION] ACCOUNTANT_WEBHOOK_URL not configured; skipping webhook delivery.")

    print(f"[ESCALATION] {payload}")
    return {
        "escalated": True,
        "webhook_sent": webhook_sent,
        "message": "Tu consulta fue derivada al contador. Se comunicará con vos a la brevedad.",
    }


def get_current_datetime() -> dict:
    now = datetime.now()
    weekday_map = {
        "Monday": "lunes",
        "Tuesday": "martes",
        "Wednesday": "miércoles",
        "Thursday": "jueves",
        "Friday": "viernes",
        "Saturday": "sábado",
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
    result = TOOL_MAP[name](**params)
    log_tool_call(tool_name=name, input=params, output=result)
    return json.dumps(result, ensure_ascii=False)
