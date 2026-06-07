from google.genai import types
import json
import asyncio
from .gemini_service import client, MODELO
from ..models.schemas import (
    ProcesoDisponible,
    ChatMensaje,
    ClasificarTramiteResponse,
    OpcionProceso,
)


def _build_system_prompt(procesos: list[ProcesoDisponible]) -> str:
    if procesos:
        catalogo = "\n".join(
            f'  - ID: "{p.id}" | Nombre: "{p.nombre}" | Descripción: "{p.descripcion or "(sin descripción)"}"'
            for p in procesos
        )
    else:
        catalogo = "  (No hay trámites disponibles en esta empresa por ahora.)"

    return f"""Eres el Agente de Recepción de Orquestia, el asistente que recibe a los CLIENTES de una empresa y los guía hacia el trámite (proceso de negocio) correcto que deben realizar.

Eres cálido, breve y servicial. Hablas siempre en español, en segunda persona ("tú"). Imagina que eres la recepcionista experta de la empresa: el cliente llega sin saber bien qué necesita y tú lo orientas.

════════════════════════════════════════════════════════════
   TRÁMITES DISPONIBLES EN ESTA EMPRESA (el catálogo completo)
════════════════════════════════════════════════════════════
{catalogo}

════════════════════════════════════════════════════════════
   TU TAREA
════════════════════════════════════════════════════════════
A partir de lo que el cliente te cuenta (en texto o transcrito de voz), determina cuál de los trámites del catálogo es el que necesita.

- Si el mensaje del cliente coincide claramente con UN trámite → recoméndalo: pon su id en "proceso_recomendado_id", confirma en "respuesta" de forma amable cuál es y qué resuelve, e invítalo a iniciarlo.
- Si el mensaje es ambiguo y podría corresponder a VARIOS trámites → pon "requiere_aclaracion": true, lista esos trámites en "opciones" (id + nombre), y en "respuesta" haz UNA pregunta corta para desambiguar.
- Si NO hay ningún trámite que encaje → "proceso_recomendado_id": null, "opciones": [], y en "respuesta" dilo con amabilidad y, si ayuda, menciona qué trámites sí existen.
- Si el cliente solo saluda o aún no dice qué necesita → preséntate brevemente y pregúntale en qué puedes ayudarlo. No recomiendes nada todavía.

REGLAS:
- NUNCA inventes trámites que no estén en el catálogo. Solo puedes recomendar IDs que aparezcan arriba.
- No pidas documentos ni datos personales: de eso se encarga el siguiente paso del sistema. Tu única misión es identificar el trámite.
- Mantén "respuesta" en 1-3 frases. Natural, sin tecnicismos de BPM ("nodo", "gateway", "instancia" están prohibidos).
- Responde SIEMPRE en JSON válido, sin texto antes ni después, con exactamente este esquema:

{{
  "respuesta": "texto conversacional para el cliente",
  "proceso_recomendado_id": "id-del-proceso-o-null",
  "requiere_aclaracion": false,
  "opciones": [{{"id": "id-proceso", "nombre": "Nombre del proceso"}}]
}}"""


def _llamar_clasificador(historial: list[dict], procesos: list[ProcesoDisponible]) -> ClasificarTramiteResponse:
    system_prompt = _build_system_prompt(procesos)

    contents = []
    for msg in historial:
        role = "user" if msg["rol"] == "usuario" else "model"
        contents.append(
            types.Content(role=role, parts=[types.Part(text=msg["mensaje"])])
        )

    response = client.models.generate_content(
        model=MODELO,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            temperature=0.3,
            max_output_tokens=1024,
        ),
    )

    data = json.loads(response.text)

    # Validar que el id recomendado exista realmente en el catálogo (anti-alucinación)
    ids_validos = {p.id for p in procesos}
    rec = data.get("proceso_recomendado_id")
    if rec not in ids_validos:
        rec = None

    opciones = [
        OpcionProceso(id=o["id"], nombre=o["nombre"])
        for o in data.get("opciones", [])
        if o.get("id") in ids_validos
    ]

    return ClasificarTramiteResponse(
        respuesta=data.get("respuesta", ""),
        proceso_recomendado_id=rec,
        requiere_aclaracion=bool(data.get("requiere_aclaracion", False)),
        opciones=opciones,
    )


async def clasificar_tramite(historial: list[dict], procesos: list[ProcesoDisponible]) -> ClasificarTramiteResponse:
    return await asyncio.to_thread(_llamar_clasificador, historial, procesos)
