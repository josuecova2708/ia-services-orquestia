"""
Definición compartida del modelo de predicción BPM (Fase 5 — Deep Learning).

Este módulo es la ÚNICA fuente de verdad de:
  - El orden y significado de las features (FEATURE_NAMES + vector_features).
  - La arquitectura de la red Keras (build_model).

Lo usan tanto el entrenamiento (scripts/train_model.py) como la inferencia
(app/services/prediccion_service.py), garantizando que las features se
construyan EXACTAMENTE igual en ambos lados.

Decisión de diseño: TODAS las features son numéricas y GENERALIZABLES — no
dependen de IDs concretos de Mongo (departamentos, usuarios). Así el modelo,
entrenado con datos sintéticos, funciona sobre cualquier empresa real sin
necesidad de un encoder de categorías que mapee IDs no vistos. La "lentitud"
de un departamento/nodo ya queda capturada por `duracion_historica_avg`.
"""

from __future__ import annotations

# Orden canónico de las features que entran a la red (shape = 6).
FEATURE_NAMES = [
    "hora_creacion",          # 0-23: hora en que se creó la tarea
    "dia_semana",             # 0=lunes ... 6=domingo
    "es_fin_semana",          # 1 si sábado/domingo, 0 si no
    "carga_funcionario",      # nº de tareas pendientes/en progreso del asignado
    "duracion_historica_avg", # minutos: promedio histórico de ese tipo de nodo
    "intentos",               # nº de reintentos (loops) acumulados en la tarea
]

N_FEATURES = len(FEATURE_NAMES)

# Umbral de "demora": una tarea se considera demorada si tarda más de este
# múltiplo de su duración histórica esperada. Usado para etiquetar y para
# interpretar el riesgo.
UMBRAL_DEMORA = 1.5


def vector_features(hora_creacion: int, dia_semana: int, carga_funcionario: int,
                    duracion_historica_avg: float, intentos: int) -> list[float]:
    """Construye el vector de features en el orden canónico de FEATURE_NAMES."""
    es_fin_semana = 1 if dia_semana >= 5 else 0
    return [
        float(hora_creacion),
        float(dia_semana),
        float(es_fin_semana),
        float(carga_funcionario),
        float(duracion_historica_avg),
        float(intentos),
    ]


def build_model(n_features: int = N_FEATURES):
    """
    Red neuronal con DOS cabezas (multi-tarea):
      - 'duracion': regresión → minutos estimados (sobre target estandarizado)
      - 'riesgo':   clasificación binaria → probabilidad de demora (0-1)

    El tronco compartido aprende representaciones útiles para ambas tareas.
    """
    from tensorflow import keras
    from tensorflow.keras import layers

    inputs = keras.Input(shape=(n_features,), name="features")
    x = layers.Dense(64, activation="relu")(inputs)
    x = layers.Dropout(0.2)(x)
    x = layers.Dense(32, activation="relu")(x)

    duracion_out = layers.Dense(1, name="duracion")(x)
    riesgo_out = layers.Dense(1, activation="sigmoid", name="riesgo")(x)

    model = keras.Model(inputs=inputs, outputs=[duracion_out, riesgo_out])
    model.compile(
        optimizer="adam",
        loss={"duracion": "mse", "riesgo": "binary_crossentropy"},
        loss_weights={"duracion": 1.0, "riesgo": 1.0},
        metrics={"riesgo": ["accuracy"]},
    )
    return model
