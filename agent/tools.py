import json
import requests
from datetime import datetime
from rag.retriever import buscar_similar
from observability.logger import log_tool_call


TOOLS_SCHEMA = [
    {
        "name": "buscar_en_documentos",
        "description": "Busca información en los documentos internos del estudio contable (normativas AFIP, calendarios, guías). Usar siempre como primer recurso ante dudas fiscales.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Consulta en lenguaje natural"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "consultar_vencimientos",
        "description": "Devuelve fechas de vencimiento fiscal para un tipo de contribuyente y mes dado.",
        "parameters": {
            "type": "object",
            "properties": {
                "tipo_contribuyente": {"type": "string", "enum": ["monotributo", "responsable_inscripto", "empleado_relacion_dependencia"]},
                "mes": {"type": "integer", "description": "Número de mes (1-12)"}
            },
            "required": ["tipo_contribuyente", "mes"]
        }
    },
    {
        "name": "escalar_consulta",
        "description": "Registra la consulta para atención humana y notifica al contador. Usar cuando la consulta excede el dominio del agente.",
        "parameters": {
            "type": "object",
            "properties": {
                "motivo": {"type": "string"},
                "datos_cliente": {"type": "string"}
            },
            "required": ["motivo"]
        }
    },
    {
        "name": "obtener_fecha_hora",
        "description": "Devuelve la fecha y hora actuales (Buenos Aires). Usar para calcular vencimientos relativos.",
        "parameters": {"type": "object", "properties": {}}
    }
]

def buscar_en_documentos(query: str) -> dict:
    """RAG: búsqueda semántica en Supabase pgvector"""
    try:
        resultados = buscar_similar(query, top_k=3)
        if not resultados:
            return {
                "encontrado": False,
                "mensaje": "No se encontraron documentos relevantes para esta consulta."
            }
        return {
            "encontrado": True,
            "fragmentos": [
                {"texto": r["content"], "fuente": r["source"], "similitud": r["similarity"]}
                for r in resultados
            ]
        }
    except Exception as e:
        return {"error": str(e), "encontrado": False}

VENCIMIENTOS = {
    "monotributo": {
        6: [{"obligacion": "Pago mensual monotributo", "vencimiento": "20/06/2026"},
            {"obligacion": "Recategorización semestral", "vencimiento": "20/06/2026"}],
        7: [{"obligacion": "Pago mensual monotributo", "vencimiento": "21/07/2026"}],
    },
    "responsable_inscripto": {
        6: [{"obligacion": "Declaración jurada IVA mensual", "vencimiento": "18/06/2026"},
            {"obligacion": "Anticipos Ganancias", "vencimiento": "13/06/2026"}],
        7: [{"obligacion": "Declaración jurada IVA mensual", "vencimiento": "17/07/2026"}],
    }
}

def consultar_vencimientos(tipo_contribuyente: str, mes: int) -> dict:
    venc = VENCIMIENTOS.get(tipo_contribuyente, {}).get(mes, [])
    if not venc:
        return {"tipo": tipo_contribuyente, "mes": mes, "vencimientos": [],
                "nota": "No hay vencimientos registrados para este período."}
    return {"tipo": tipo_contribuyente, "mes": mes, "vencimientos": venc}


def escalar_consulta(motivo: str, datos_cliente: str = "") -> dict:
    """Registra la consulta y (en producción) dispara webhook al contador"""
    payload = {
        "timestamp": datetime.now().isoformat(),
        "motivo": motivo,
        "datos_cliente": datos_cliente,
        "estado": "pendiente"
    }
    # TODO producción: requests.post(WEBHOOK_URL, json=payload)
    print(f"[ESCALADO] {payload}")
    return {"escalado": True, "mensaje": "Tu consulta fue derivada al contador. Te contactarán a la brevedad."}


def obtener_fecha_hora() -> dict:
    now = datetime.now()
    return {
        "fecha": now.strftime("%d/%m/%Y"),
        "hora": now.strftime("%H:%M"),
        "mes": now.month,
        "dia_semana": now.strftime("%A")
    }

TOOL_MAP = {
    "buscar_en_documentos": buscar_en_documentos,
    "consultar_vencimientos": consultar_vencimientos,
    "escalar_consulta": escalar_consulta,
    "obtener_fecha_hora": obtener_fecha_hora
}

def ejecutar_tool(nombre: str, params: dict) -> str:
    if nombre not in TOOL_MAP:
        return json.dumps({"error": f"Tool '{nombre}' no encontrada"})
    resultado = TOOL_MAP[nombre](**params)
    log_tool_call(tool_name=nombre, input=params, output=resultado)
    return json.dumps(resultado, ensure_ascii=False)
