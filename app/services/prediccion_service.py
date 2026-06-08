"""
Servicio de inferencia del modelo predictivo BPM (Fase 5).

Recibe del backend las tareas pendientes de una instancia con sus features ya
calculadas, corre el modelo TensorFlow (cargado una sola vez como singleton),
agrega los resultados a nivel de instancia y pide a Gemini que traduzca los
números a recomendaciones accionables en español.

El backend (Spring) es quien calcula las features porque tiene los datos en
Mongo; aquí solo se ejecuta el modelo + la capa de lenguaje natural.
"""

from __future__ import annotations

import json
import os
import re
import threading

import numpy as np

from ..models.schemas import (
    PrediccionRequest,
    PrediccionResponse,
    NodoRiesgo,
)
from ..ml.modelo_bpm import vector_features, UMBRAL_DEMORA

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODEL_PATH = os.path.join(_BASE_DIR, "ml", "modelo_bpm.keras")
_SCALERS_PATH = os.path.join(_BASE_DIR, "ml", "scalers.pkl")

# Umbral para considerar una tarea "en riesgo" en la respuesta.
_RIESGO_THRESHOLD = 0.5

_lock = threading.Lock()
_model = None
_scalers = None


def cargar_modelo():
    """Carga modelo + scalers una sola vez (idempotente). Llamado en el startup."""
    global _model, _scalers
    if _model is not None:
        return
    with _lock:
        if _model is not None:
            return
        if not os.path.exists(_MODEL_PATH) or not os.path.exists(_SCALERS_PATH):
            raise FileNotFoundError(
                "Modelo no entrenado. Corre: python scripts/generate_training_data.py "
                "&& python scripts/train_model.py"
            )
        import joblib
        from tensorflow import keras

        _model = keras.models.load_model(_MODEL_PATH)
        _scalers = joblib.load(_SCALERS_PATH)


def modelo_disponible() -> bool:
    return os.path.exists(_MODEL_PATH) and os.path.exists(_SCALERS_PATH)


def _modelo_info() -> dict:
    s = _scalers or {}
    return {
        "features": s.get("feature_names", []),
        "registros_entrenamiento": s.get("n_total"),
        "val_accuracy": s.get("val_accuracy"),
        "umbral_demora": UMBRAL_DEMORA,
    }


def predecir(req: PrediccionRequest) -> PrediccionResponse:
    cargar_modelo()

    if not req.tareas:
        return PrediccionResponse(
            instancia_id=req.instancia_id,
            resumen="La instancia no tiene tareas pendientes para analizar.",
            modelo_info=_modelo_info(),
        )

    # 1. Matriz de features en el orden canónico
    X = np.array([
        vector_features(
            t.hora_creacion, t.dia_semana, t.carga_funcionario,
            t.duracion_historica_avg, t.intentos,
        )
        for t in req.tareas
    ], dtype="float32")

    Xs = _scalers["x_scaler"].transform(X)
    dur_pred, riesgo_pred = _model.predict(Xs, verbose=0)
    duraciones = _scalers["y_scaler"].inverse_transform(dur_pred).ravel()
    riesgos = riesgo_pred.ravel()

    # 2. Resultado por tarea
    tareas_riesgo = []
    for t, dur, r in zip(req.tareas, duraciones, riesgos):
        tareas_riesgo.append(NodoRiesgo(
            tarea_id=t.tarea_id,
            nodo_label=t.nodo_label,
            funcionario=t.funcionario,
            riesgo=round(float(r), 3),
            duracion_estimada_min=round(float(max(0.0, dur)), 1),
            # eco de las features de entrada (datos en crudo)
            hora_creacion=t.hora_creacion,
            dia_semana=t.dia_semana,
            carga_funcionario=t.carga_funcionario,
            duracion_historica_avg=round(float(t.duracion_historica_avg), 1),
            intentos=t.intentos,
        ))

    # 3. Agregación a nivel instancia
    riesgo_global = max((n.riesgo for n in tareas_riesgo), default=0.0)
    duracion_total = round(sum(n.duracion_estimada_min for n in tareas_riesgo), 1)
    en_riesgo = sorted(
        [n for n in tareas_riesgo if n.riesgo >= _RIESGO_THRESHOLD],
        key=lambda n: n.riesgo, reverse=True,
    )

    # 4. Lenguaje natural (Gemini con fallback)
    recomendaciones, resumen = _recomendaciones(req, tareas_riesgo, riesgo_global, en_riesgo)

    return PrediccionResponse(
        instancia_id=req.instancia_id,
        riesgo_global=round(float(riesgo_global), 3),
        duracion_estimada_total_min=duracion_total,
        nodos_en_riesgo=en_riesgo,
        tareas=sorted(tareas_riesgo, key=lambda n: n.riesgo, reverse=True),
        recomendaciones=recomendaciones,
        resumen=resumen,
        modelo_info=_modelo_info(),
    )


# ─── Capa de lenguaje natural ─────────────────────────────────────────────────

def _recomendaciones(req, tareas_riesgo, riesgo_global, en_riesgo):
    """Genera recomendaciones con Gemini; si falla, usa reglas simples."""
    try:
        return _recomendaciones_gemini(req, tareas_riesgo, riesgo_global)
    except Exception:
        return _recomendaciones_fallback(riesgo_global, en_riesgo)


def _recomendaciones_gemini(req, tareas_riesgo, riesgo_global):
    from google.genai import types
    from .gemini_service import client, MODELO

    detalle = "\n".join(
        f'  - "{n.nodo_label}" (responsable: {n.funcionario or "sin asignar"}): '
        f"riesgo {n.riesgo:.0%}, duración estimada {n.duracion_estimada_min:.0f} min"
        for n in tareas_riesgo
    )
    nivel = "ALTO" if riesgo_global >= 0.7 else ("MEDIO" if riesgo_global >= 0.4 else "BAJO")

    system_prompt = (
        "Eres un analista de operaciones BPM. A partir de las predicciones de un modelo de "
        "Deep Learning sobre las tareas pendientes de un trámite, das recomendaciones "
        "concretas y accionables para reducir el riesgo de demora. NO inventas datos: te "
        "basas solo en los números dados. Respondes SIEMPRE en JSON válido sin texto extra:\n"
        '{ "resumen": "1-2 frases sobre el estado general del trámite", '
        '"recomendaciones": ["acción concreta 1", "acción concreta 2", "..."] }\n'
        "Entre 2 y 4 recomendaciones, en español, específicas (mencionando el nodo o "
        "responsable cuando aplique). Si el riesgo global es bajo, dilo y sugiere solo "
        "seguimiento rutinario."
    )
    user = (
        f"Trámite: {req.proceso_nombre or 'proceso'}\n"
        f"Riesgo global: {riesgo_global:.0%} ({nivel})\n"
        f"Tareas pendientes:\n{detalle}"
    )

    response = client.models.generate_content(
        model=MODELO,
        contents=[types.Content(role="user", parts=[types.Part(text=user)])],
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            temperature=0.3,
            max_output_tokens=600,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    data = _extract_json(response.text)
    recs = data.get("recomendaciones", [])
    recs = [str(r) for r in recs if str(r).strip()][:4]
    resumen = str(data.get("resumen", "")).strip()
    if not recs:
        raise ValueError("Gemini no devolvió recomendaciones")
    return recs, resumen


def _recomendaciones_fallback(riesgo_global, en_riesgo):
    if riesgo_global >= 0.7:
        recs = ["El trámite tiene alto riesgo de demora; prioriza su atención de inmediato."]
        for n in en_riesgo[:3]:
            recs.append(
                f'Revisa "{n.nodo_label}"'
                + (f" asignada a {n.funcionario}" if n.funcionario else "")
                + " — considera reasignarla o darle prioridad."
            )
        resumen = "Alto riesgo de demora en una o más tareas pendientes."
    elif riesgo_global >= 0.4:
        recs = [
            "Riesgo moderado: haz seguimiento a las tareas pendientes en las próximas horas.",
            "Verifica la carga de trabajo de los responsables involucrados.",
        ]
        resumen = "Riesgo moderado de demora."
    else:
        recs = ["El trámite avanza con normalidad; basta con seguimiento rutinario."]
        resumen = "Bajo riesgo de demora."
    return recs, resumen


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    md = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if md:
        return json.loads(md.group(1))
    obj = re.search(r"\{[\s\S]*\}", text)
    if obj:
        return json.loads(obj.group(0))
    return json.loads(text)
