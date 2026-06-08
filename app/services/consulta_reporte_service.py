from google.genai import types
import json
import re
import asyncio
from .gemini_service import client, MODELO
from ..models.schemas import (
    ProcesoDisponible,
    FuncionarioDisponible,
    ConsultaReporteSpec,
)

# Catálogo FIJO de métricas que el backend sabe calcular. El agente SOLO puede
# elegir una de estas; cualquier otra cosa → valido=false.
METRICAS = {
    "actividades_completadas_por_funcionario":
        "Ranking de funcionarios por número de actividades/tareas COMPLETADAS. Ideal para productividad ('quién hizo más', 'funcionarios más activos').",
    "carga_pendiente_por_funcionario":
        "Tareas actualmente pendientes o en progreso por funcionario (carga de trabajo actual, snapshot, no usa rango de fechas).",
    "cuellos_de_botella":
        "Actividades más lentas: tiempo promedio que tarda cada actividad en completarse.",
    "tiempos_por_proceso":
        "Duración promedio total de cada tipo de proceso completado.",
    "ejecuciones_por_proceso":
        "Cuántas ejecuciones/trámites se iniciaron de cada proceso.",
    "ejecuciones_por_estado":
        "Conteo de ejecuciones agrupadas por estado (ACTIVA, COMPLETADA, CANCELADA, ERROR).",
    "actividad_diaria":
        "Serie temporal: ejecuciones iniciadas por día (tendencia).",
}


def _build_system_prompt(
    fecha_actual: str,
    procesos: list[ProcesoDisponible],
    funcionarios: list[FuncionarioDisponible],
) -> str:
    catalogo_metricas = "\n".join(f'  - "{k}": {v}' for k, v in METRICAS.items())

    if procesos:
        catalogo_procesos = "\n".join(f'  - ID: "{p.id}" | Nombre: "{p.nombre}"' for p in procesos)
    else:
        catalogo_procesos = "  (sin procesos)"

    if funcionarios:
        catalogo_func = "\n".join(f'  - ID: "{f.id}" | Nombre: "{f.nombre}"' for f in funcionarios)
    else:
        catalogo_func = "  (sin funcionarios)"

    return f"""Eres el Generador de Reportes de Orquestia. Tu trabajo es traducir una consulta en lenguaje natural (texto o voz) de un administrador a una ESPECIFICACIÓN ESTRUCTURADA de reporte que el sistema sabe calcular.

NO conversas ni analizas datos: solo decides QUÉ métrica, con QUÉ filtros y en QUÉ formato.

La fecha de hoy es: {fecha_actual}. Úsala para interpretar expresiones de tiempo relativas.

════════════════════════════════════════════════════════════
   CATÁLOGO DE MÉTRICAS (elige EXACTAMENTE una de estas claves)
════════════════════════════════════════════════════════════
{catalogo_metricas}

════════════════════════════════════════════════════════════
   PROCESOS DE LA EMPRESA (para filtrar por proceso)
════════════════════════════════════════════════════════════
{catalogo_procesos}

════════════════════════════════════════════════════════════
   FUNCIONARIOS (para filtrar por una persona concreta)
════════════════════════════════════════════════════════════
{catalogo_func}

════════════════════════════════════════════════════════════
   CÓMO INTERPRETAR
════════════════════════════════════════════════════════════
- "metrica": la clave del catálogo que mejor responde la consulta. Si NINGUNA encaja → "valido": false y explica en "mensaje" qué SÍ puedes generar.
- Fechas ("desde"/"hasta", formato yyyy-MM-dd): interpreta lenguaje natural relativo a hoy ({fecha_actual}).
  · "junio" / "todo junio" → del día 1 al último día de junio del año en curso.
  · "esta semana" → lunes a hoy. "este mes" → día 1 del mes a hoy. "hoy" → hoy a hoy.
  · "últimos 7 días" → hoy menos 6 días a hoy. "este año" → 01-01 a hoy.
  · Si no se menciona ningún periodo → deja "desde" y "hasta" en null (histórico completo).
- "estado": ACTIVA | COMPLETADA | CANCELADA | ERROR, solo si la consulta lo menciona; si no, null.
- "proceso_id": SOLO un ID del catálogo de procesos, si la consulta nombra un proceso concreto; si no, null. NUNCA inventes IDs.
- "funcionario_id": SOLO un ID del catálogo de funcionarios, si la consulta nombra a UNA persona; si no, null. NUNCA inventes IDs.
- "limite": si pide "top N", "los 5 mejores", etc., pon ese número; si no, null.
- "orden": "desc" (mayor a menor, lo habitual en rankings) o "asc" si pide "los que menos...".
- "formato": "pdf" si pide PDF, "excel" si pide Excel/xlsx/hoja de cálculo, "pantalla" si no menciona formato.
- "titulo": un título corto y legible para el reporte, incluyendo el periodo si aplica (ej: "Funcionarios con más actividades — Junio 2026").

REGLAS:
- Responde SIEMPRE en JSON válido, sin texto antes ni después, EXACTAMENTE con este esquema:

{{
  "valido": true,
  "mensaje": "confirmación breve de lo que se generará, o explicación si no es posible",
  "metrica": "clave_del_catalogo_o_null",
  "desde": "yyyy-MM-dd o null",
  "hasta": "yyyy-MM-dd o null",
  "estado": "ESTADO o null",
  "proceso_id": "id o null",
  "funcionario_id": "id o null",
  "limite": null,
  "orden": "desc",
  "formato": "pantalla",
  "titulo": "Título del reporte"
}}"""


def _extract_json(text: str) -> dict:
    """Extrae JSON de una respuesta que puede contener bloques markdown o texto de thinking."""
    text = text.strip()
    # Si viene dentro de un bloque ```json ... ``` (a veces Gemini lo hace)
    md_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if md_match:
        return json.loads(md_match.group(1))
    # Si viene con texto antes del JSON (thinking tokens)
    obj_match = re.search(r'\{[\s\S]*\}', text)
    if obj_match:
        return json.loads(obj_match.group(0))
    return json.loads(text)


def _llamar_consulta(
    pregunta: str,
    fecha_actual: str,
    procesos: list[ProcesoDisponible],
    funcionarios: list[FuncionarioDisponible],
) -> ConsultaReporteSpec:
    system_prompt = _build_system_prompt(fecha_actual, procesos, funcionarios)

    response = client.models.generate_content(
        model=MODELO,
        contents=[types.Content(role="user", parts=[types.Part(text=pregunta)])],
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            temperature=0.1,
            max_output_tokens=1024,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )

    data = _extract_json(response.text)

    # Validaciones anti-alucinación
    metrica = data.get("metrica")
    if metrica not in METRICAS:
        metrica = None

    ids_procesos = {p.id for p in procesos}
    proceso_id = data.get("proceso_id")
    if proceso_id not in ids_procesos:
        proceso_id = None

    ids_func = {f.id for f in funcionarios}
    funcionario_id = data.get("funcionario_id")
    if funcionario_id not in ids_func:
        funcionario_id = None

    estado = data.get("estado")
    if estado not in {"ACTIVA", "COMPLETADA", "CANCELADA", "ERROR"}:
        estado = None

    formato = data.get("formato", "pantalla")
    if formato not in {"pantalla", "pdf", "excel"}:
        formato = "pantalla"

    orden = data.get("orden", "desc")
    if orden not in {"asc", "desc"}:
        orden = "desc"

    limite = data.get("limite")
    if isinstance(limite, str) and limite.isdigit():
        limite = int(limite)
    if not isinstance(limite, int) or limite <= 0:
        limite = None

    valido = bool(data.get("valido", True)) and metrica is not None
    mensaje = data.get("mensaje", "")
    if metrica is None and not mensaje:
        mensaje = "No pude identificar un reporte que coincida con tu consulta. Prueba pidiendo, por ejemplo, actividades por funcionario, tiempos por proceso o cuellos de botella."

    return ConsultaReporteSpec(
        valido=valido,
        mensaje=mensaje,
        metrica=metrica,
        desde=data.get("desde"),
        hasta=data.get("hasta"),
        estado=estado,
        proceso_id=proceso_id,
        funcionario_id=funcionario_id,
        limite=limite,
        orden=orden,
        formato=formato,
        titulo=data.get("titulo"),
    )


async def interpretar_consulta(
    pregunta: str,
    fecha_actual: str,
    procesos: list[ProcesoDisponible],
    funcionarios: list[FuncionarioDisponible],
) -> ConsultaReporteSpec:
    return await asyncio.to_thread(
        _llamar_consulta, pregunta, fecha_actual, procesos, funcionarios
    )
