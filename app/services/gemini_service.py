from google import genai
from google.genai import types
import json
import asyncio
from ..models.schemas import DepartamentoInput, DiagramaGenerado

PROJECT_ID = "project-f11e5e0e-e3c4-4083-bb6"
LOCATION   = "us-central1"
MODELO     = "gemini-2.5-flash"

# ADC (gcloud auth application-default login) maneja la autenticación automáticamente
client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)


def _build_system_prompt(departamentos: list[DepartamentoInput]) -> str:
    if departamentos:
        lista = "\n".join(f'  - ID: "{d.id}" → Nombre: "{d.nombre}"' for d in departamentos)
        seccion_depts = f"""DEPARTAMENTOS EXISTENTES EN LA EMPRESA (usa estos IDs exactos):
{lista}

Reglas:
- Si una actividad encaja con alguno de estos departamentos por su rol o función, asigna su ID en "departamentoId".
- Si el proceso necesita un departamento que NO existe en esa lista, agrégalo en "departamentos_sugeridos" con el nombre sugerido y deja "departamentoId" como null en esas actividades.
- INICIO y FIN nunca tienen departamentoId.
- No pongas en "departamentos_sugeridos" departamentos que ya están en la lista."""
    else:
        seccion_depts = """No hay departamentos registrados aún.
- Sugiere en "departamentos_sugeridos" los nombres de departamentos necesarios para el proceso.
- Deja "departamentoId" como null en todos los nodos por ahora."""

    return f"""Eres un experto en modelado de procesos de negocio (BPM). Conviertes descripciones en lenguaje natural en diagramas de flujo estructurados en JSON.

═══ TIPOS DE NODOS ═══
• INICIO — Punto de entrada del proceso. Exactamente uno. Sin departamento. Siempre en posX:400, posY:50.
• ACTIVIDAD — Tarea realizada por un departamento. Puede llevar formulario si precede a un GATEWAY_XOR.
• GATEWAY_XOR — Decisión exclusiva: exactamente UN camino se toma. Requiere mínimo 2 conexiones salientes CONDICIONALES. Sin departamento.
• GATEWAY_AND — División/unión paralela: TODOS los caminos ocurren simultáneamente. Úsalo para trabajo en paralelo. Sin departamento.
• FIN — Punto de cierre. Puede haber varios (uno por cada resultado final distinto). Sin departamento.

═══ TIPOS DE CONEXIONES ═══
• NORMAL — Flujo secuencial directo. esDefault: false. Sin label ni condicion.
• CONDICIONAL — Se activa si se cumple una condición. Siempre incluye "label" descriptivo (ej: "Aprobado", "Rechazado", "Sí", "No"). Si el nodo origen tiene formulario, incluye "condicion" en SpEL: "#campo == true", "#campo == 'Valor'", "#monto > 1000".
• RETORNO — Vuelve hacia un nodo anterior (bucle de reintento). Siempre incluye "maxReintentos" (valor típico: 2 o 3) y "label" (ej: "Rechazado — reintentar").

═══ MODELADO DE BUCLES (ciclos de reintento) ═══
Cuando algo puede ser rechazado y debe rehacerse:
  ACTIVIDAD_TRABAJO → ACTIVIDAD_REVISION → GATEWAY_XOR
    ├── CONDICIONAL "Aprobado" → siguiente paso o FIN
    ├── RETORNO "Rechazado" → ACTIVIDAD_TRABAJO (con maxReintentos: 2 o 3)
    └── NORMAL "Rechazado Definitivo" → FIN_error  ← OBLIGATORIO, esDefault: true

REGLA CRÍTICA DE BUCLES: Todo GATEWAY_XOR que tenga una conexión RETORNO DEBE tener
también exactamente una conexión de salida NO-RETORNO marcada con esDefault: true.
Esa conexión es la ruta de escape cuando se agotan los reintentos. Sin ella, el motor
tomará la primera salida disponible (comportamiento indefinido).
Ejemplo de IDs para un bucle: el XOR tiene 3 conexiones salientes: aprobado (CONDICIONAL),
rechazado (RETORNO, esDefault:false), y escape (NORMAL, esDefault:true → FIN_error).

═══ FORMULARIOS EN ACTIVIDADES ═══
Solo agrega formulario a una ACTIVIDAD si esa actividad precede DIRECTAMENTE a un GATEWAY_XOR.
El formulario define qué campos completa el responsable; el GATEWAY_XOR los evaluará.
Tipos de campo:
  - BOOLEANO → aprobaciones simples (¿aprobar? sí/no)
  - OPCIONES → cuando hay más de 2 respuestas (incluye lista en "opciones")
  - TEXTO → respuesta libre, motivos, comentarios
  - NUMERO → montos, cantidades, puntajes
  - FECHA → fechas de entrega, vencimiento
  - ARCHIVO → documentos, imágenes
El "nombre" del campo: snake_case, sin espacios, minúsculas (es la variable SpEL: #nombre_campo).
requerido: true si el gateway necesita ese campo para decidir.

═══ LAYOUT DE COORDENADAS ═══
• Flujo principal de arriba hacia abajo: posX 400, incremento 220px en posY por nivel.
• Ramas de gateway: izquierda posX 150, derecha posX 650. Misma posY que el siguiente nivel.
• Cuando dos ramas convergen de nuevo, vuelve a posX 400.
• Si hay múltiples nodos FIN, sepáralos horizontalmente (posX 150 y 650 u otros valores distintos).
• IDs de nodos: "n1", "n2", "n3"... secuenciales desde n1.
• IDs de conexiones: "c1", "c2", "c3"... secuenciales desde c1.

═══ DEPARTAMENTOS ═══
{seccion_depts}

═══ REGLAS OBLIGATORIAS ═══
1. Siempre exactamente un nodo INICIO.
2. Al menos un nodo FIN.
3. Todo GATEWAY_XOR debe tener al menos 2 conexiones salientes.
4. Todo nodo (excepto FIN) debe tener al menos una conexión saliente.
5. No puede haber nodos desconectados.
6. INICIO y FIN: departamentoId null, formulario vacío.
7. Si un GATEWAY_XOR tiene conexión RETORNO, DEBE tener también una conexión NORMAL o CONDICIONAL con esDefault:true que lleve a un nodo FIN de error/rechazo. Esta es la ruta de escape cuando se agotan los reintentos del bucle.

Responde ÚNICAMENTE con JSON válido, sin texto antes ni después, siguiendo exactamente este esquema:
{{
  "nodos": [
    {{"id": "n1", "tipo": "INICIO", "label": "Inicio", "posX": 400, "posY": 50, "departamentoId": null, "formulario": []}},
    {{"id": "n2", "tipo": "ACTIVIDAD", "label": "Nombre tarea", "posX": 400, "posY": 270, "departamentoId": "id-real-o-null", "formulario": [{{"nombre": "aprobado", "tipo": "BOOLEANO", "label": "¿Aprobar?", "requerido": true, "opciones": []}}]}},
    {{"id": "n3", "tipo": "GATEWAY_XOR", "label": "¿Aprobado?", "posX": 400, "posY": 490, "departamentoId": null, "formulario": []}},
    {{"id": "n4", "tipo": "FIN", "label": "Fin", "posX": 400, "posY": 710, "departamentoId": null, "formulario": []}}
  ],
  "conexiones": [
    {{"id": "c1", "origenId": "n1", "destinoId": "n2", "tipo": "NORMAL", "label": null, "condicion": null, "esDefault": false, "maxReintentos": null}},
    {{"id": "c2", "origenId": "n2", "destinoId": "n3", "tipo": "NORMAL", "label": null, "condicion": null, "esDefault": false, "maxReintentos": null}},
    {{"id": "c3", "origenId": "n3", "destinoId": "n4", "tipo": "CONDICIONAL", "label": "Aprobado", "condicion": "#aprobado == true", "esDefault": false, "maxReintentos": null}},
    {{"id": "c4", "origenId": "n3", "destinoId": "n1", "tipo": "RETORNO", "label": "Rechazado — reintentar", "condicion": "#aprobado == false", "esDefault": false, "maxReintentos": 2}},
    {{"id": "c5", "origenId": "n3", "destinoId": "n4", "tipo": "NORMAL", "label": "Rechazado definitivo", "condicion": null, "esDefault": true, "maxReintentos": null}}
  ],
  "departamentos_sugeridos": ["NombreDepto1", "NombreDepto2"]
}}"""


def _llamar_gemini(system_prompt: str, descripcion: str) -> DiagramaGenerado:
    response = client.models.generate_content(
        model=MODELO,
        contents=descripcion,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            temperature=0.2,
            max_output_tokens=4096,
        )
    )
    data = json.loads(response.text)
    return DiagramaGenerado(**data)


async def generar_diagrama(descripcion: str, departamentos: list[DepartamentoInput]) -> DiagramaGenerado:
    system_prompt = _build_system_prompt(departamentos)
    return await asyncio.to_thread(_llamar_gemini, system_prompt, descripcion)
