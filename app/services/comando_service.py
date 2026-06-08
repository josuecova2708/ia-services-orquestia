from google.genai import types
import json
import asyncio
from .gemini_service import client, MODELO
from ..models.schemas import (
    NodoComando,
    DepartamentoInput,
    ComandoDiagramaResponse,
    AccionDiagrama,
)


def _build_system_prompt(nodos: list[NodoComando], departamentos: list[DepartamentoInput]) -> str:
    lista_nodos = "\n".join(
        f'  - id: "{n.id}" | nombre: "{n.label}" | tipo: {n.tipo}'
        f' | departamentoId: {n.departamentoId or "null"} | autoservicio: {str(n.responsableCliente).lower()}'
        for n in nodos
    ) or "  (no hay nodos)"

    lista_depts = "\n".join(
        f'  - id: "{d.id}" | nombre: "{d.nombre}"' for d in departamentos
    ) or "  (no hay departamentos)"

    return f"""Eres un asistente que interpreta comandos en lenguaje natural para editar un diagrama de proceso (BPM) y los convierte en acciones estructuradas.

NODOS ACTUALES DEL DIAGRAMA:
{lista_nodos}

DEPARTAMENTOS DE LA EMPRESA:
{lista_depts}

ACCIONES QUE PUEDES DEVOLVER (solo estas cuatro):
1. "asignar_departamento" → asignar una ACTIVIDAD a un departamento. Campos: nodoId, departamentoId.
2. "renombrar" → cambiar el nombre/label de un nodo. Campos: nodoId, nuevoLabel.
3. "autoservicio" → marcar/desmarcar que una ACTIVIDAD la realiza el cliente. Campos: nodoId, valor (true para activar, false para quitar).
4. "eliminar" → eliminar un nodo del diagrama. Campos: nodoId.

REGLAS:
- Identifica el nodo objetivo por su nombre (coincidencia aproximada, ignora mayúsculas/acentos). Devuelve SIEMPRE su "id" exacto en "nodoId".
- Para "asignar_departamento", identifica el departamento por su nombre y devuelve su "id" exacto en "departamentoId".
- Solo asigna departamento a nodos tipo ACTIVIDAD. INICIO, FIN y GATEWAYS no llevan departamento.
- Si el comando no coincide con ningún nodo o departamento existente, NO inventes: devuelve "acciones" vacío y explica en "mensaje".
- Un comando puede generar varias acciones si menciona varias cosas.
- "mensaje" es un texto corto en español confirmando lo que se hará (o por qué no se pudo).

Responde ÚNICAMENTE con JSON válido con este esquema:
{{
  "acciones": [
    {{"tipo": "asignar_departamento", "nodoId": "n2", "departamentoId": "dep1", "nuevoLabel": null, "valor": null}}
  ],
  "mensaje": "Asigné la actividad 'Revisar solicitud' al departamento Legal."
}}"""


def _llamar_comando(comando: str, nodos: list[NodoComando], departamentos: list[DepartamentoInput]) -> ComandoDiagramaResponse:
    system_prompt = _build_system_prompt(nodos, departamentos)

    response = client.models.generate_content(
        model=MODELO,
        contents=comando,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            temperature=0.1,
            max_output_tokens=1024,
        ),
    )
    data = json.loads(response.text)

    ids_nodos = {n.id for n in nodos}
    ids_depts = {d.id for d in departamentos}
    tipos_validos = {"asignar_departamento", "renombrar", "autoservicio", "eliminar"}

    acciones = []
    for a in data.get("acciones", []):
        tipo = a.get("tipo")
        nodo_id = a.get("nodoId")
        if tipo not in tipos_validos or nodo_id not in ids_nodos:
            continue
        if tipo == "asignar_departamento" and a.get("departamentoId") not in ids_depts:
            continue
        acciones.append(AccionDiagrama(
            tipo=tipo,
            nodoId=nodo_id,
            departamentoId=a.get("departamentoId"),
            nuevoLabel=a.get("nuevoLabel"),
            valor=a.get("valor"),
        ))

    return ComandoDiagramaResponse(acciones=acciones, mensaje=data.get("mensaje", ""))


async def ejecutar_comando(comando: str, nodos: list[NodoComando], departamentos: list[DepartamentoInput]) -> ComandoDiagramaResponse:
    return await asyncio.to_thread(_llamar_comando, comando, nodos, departamentos)
