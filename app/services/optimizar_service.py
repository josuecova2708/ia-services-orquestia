from google.genai import types
import asyncio
import json
from .gemini_service import client, MODELO
from ..models.schemas import OptimizarDiagramaRequest, OptimizarDiagramaResponse

_SYSTEM_PROMPT = """Eres un experto en modelado BPM (Business Process Management).
Recibirás un diagrama BPM en JSON y debes OPTIMIZARLO sin cambiar su propósito fundamental.

═══ REGLAS DE CONEXIONES (crítico para que el motor BPM funcione) ═══

CONDICIONAL:
- Siempre tiene "label" no vacío (ej: "Aprobado", "Rechazado", "Sí", "No", "Mayor a 1000").
- Si el nodo ACTIVIDAD que precede al GATEWAY_XOR tiene un formulario con campo "nombre_campo",
  la condición se escribe en SpEL: "#nombre_campo == true", "#nombre_campo == false",
  "#nombre_campo == 'Valor'", "#nombre_campo > 1000".
- Si la conexión CONDICIONAL ya tiene "condicion" correcta, NO la cambies.
- Si le falta "condicion" y el gateway tiene formulario disponible, añádela.
- Si le falta "label", ponle uno descriptivo según el contexto.

RETORNO:
- Siempre tiene "label" (ej: "Rechazado — reintentar", "Necesita correcciones").
- Siempre tiene "maxReintentos" con valor entero (2 o 3 si no está definido).
- Siempre tiene "esDefault": false.
- Si le faltan estos campos, añádelos.

NORMAL con esDefault:true (ruta de escape):
- Obligatoria en todo GATEWAY_XOR que tenga al menos una conexión RETORNO.
- Su destino debe ser un nodo FIN (representa el camino cuando se agotan los reintentos).
- Si falta, créala como nueva conexión con id único (ej: "c_escape_<gateway_id>").

NORMAL sin condición:
- "label": null, "condicion": null, "esDefault": false, "maxReintentos": null.

═══ CAMBIOS QUE SÍ PUEDES HACER ═══
- Renombrar nodos (label) con etiquetas más formales, claras y en español profesional.
- Mejorar o añadir "label" y "condicion" en conexiones CONDICIONAL que los tengan vacíos/nulos.
- Completar "maxReintentos" y "label" en conexiones RETORNO que los tengan vacíos/nulos.
- Agregar la conexión de escape (NORMAL, esDefault:true → FIN) si falta en un XOR con RETORNO.
- Agregar GATEWAY_XOR de control de calidad si hay ACTIVIDADES → FIN directas que deberían tener aprobación.
- Limpiar formularios en ACTIVIDADES que NO preceden directamente a un GATEWAY_XOR (vaciar a []).
- Ajustar posiciones (posX, posY) para mejor legibilidad vertical (incremento de 220px entre niveles).

═══ CAMBIOS QUE NO DEBES HACER ═══
- NO cambies el departamentoId de ningún nodo — es una asignación real del cliente.
- NO cambies el campo "nombre" (snake_case) de ningún CampoFormulario — es la variable SpEL.
- NO cambies las expresiones SpEL ("condicion") que ya existen y son correctas.
- NO cambies el tipo de ningún nodo.
- NO elimines nodos ni conexiones existentes (salvo conexiones claramente inválidas).
- NO añadas departamentos nuevos.
- NO cambies los IDs de nodos ni conexiones existentes.

═══ VALIDACIONES FINALES ═══
- Todo GATEWAY_XOR con RETORNO tiene una conexión NORMAL con esDefault:true hacia un FIN.
- Todo GATEWAY_XOR tiene al menos 2 conexiones salientes.
- Toda conexión CONDICIONAL tiene label no vacío.
- Toda conexión RETORNO tiene maxReintentos (entero) y label no vacío.
- El diagrama tiene exactamente 1 nodo INICIO.

═══ CAMPO cambios_realizados ═══
Lista de strings describiendo cada cambio en primera persona y en español.
Ejemplos: "Renombré 'Tarea 1' → 'Revisión de Documentación'",
          "Añadí condición SpEL '#aprobado == true' a la conexión 'Aprobado'",
          "Completé maxReintentos: 2 en la conexión RETORNO 'Rechazado — reintentar'",
          "Agregué conexión de escape al GATEWAY_XOR '¿Aprobado?'".
Si el diagrama ya está correcto y no necesita cambios, devuelve cambios_realizados vacío.

Responde ÚNICAMENTE con JSON válido, sin texto antes ni después:
{
  "nodos": [...],
  "conexiones": [...],
  "cambios_realizados": ["..."]
}"""


def _llamar_optimizar(request: OptimizarDiagramaRequest) -> OptimizarDiagramaResponse:
    payload = {
        "nodos": request.nodos,
        "conexiones": request.conexiones,
        "departamentos_disponibles": [d.model_dump() for d in request.departamentos],
    }

    response = client.models.generate_content(
        model=MODELO,
        contents=json.dumps(payload, ensure_ascii=False),
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0.2,
            max_output_tokens=32768,
        )
    )
    data = json.loads(response.text)
    return OptimizarDiagramaResponse(**data)


async def optimizar_diagrama(request: OptimizarDiagramaRequest) -> OptimizarDiagramaResponse:
    return await asyncio.to_thread(_llamar_optimizar, request)
