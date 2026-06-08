"""
Entrena el modelo predictivo BPM (Fase 5) con los datos sintéticos.

Pipeline:
  1. Carga data/training_data.json
  2. Arma X (6 features) e y (duración + riesgo)
  3. Estandariza X y el target de duración (guarda los scalers)
  4. Entrena la red de 2 cabezas con EarlyStopping
  5. Guarda modelo (.keras) + scalers (.pkl) en app/ml/

Uso (desde la raíz del microservicio):
    python scripts/train_model.py

Requisitos: tensorflow, scikit-learn, numpy, joblib  (ver requirements.txt)
"""

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.ml.modelo_bpm import FEATURE_NAMES, build_model  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "training_data.json")
ML_DIR = os.path.join(BASE_DIR, "app", "ml")
MODEL_PATH = os.path.join(ML_DIR, "modelo_bpm.keras")
SCALERS_PATH = os.path.join(ML_DIR, "scalers.pkl")


def cargar_datos():
    if not os.path.exists(DATA_PATH):
        sys.exit(f"No existe {DATA_PATH}. Corre primero: python scripts/generate_training_data.py")
    with open(DATA_PATH, encoding="utf-8") as f:
        filas = json.load(f)

    X = np.array([[fila[name] for name in FEATURE_NAMES] for fila in filas], dtype="float32")
    y_dur = np.array([[fila["duracion_real_minutos"]] for fila in filas], dtype="float32")
    y_risk = np.array([[fila["hubo_demora"]] for fila in filas], dtype="float32")
    return X, y_dur, y_risk


def main():
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from tensorflow import keras
    import joblib

    X, y_dur, y_risk = cargar_datos()
    print(f"Datos: {len(X)} registros · {X.shape[1]} features")

    # Estandarización
    x_scaler = StandardScaler().fit(X)
    y_scaler = StandardScaler().fit(y_dur)
    Xs = x_scaler.transform(X)
    y_dur_s = y_scaler.transform(y_dur)

    # Split train/val
    (X_tr, X_val, ydur_tr, ydur_val, yr_tr, yr_val) = train_test_split(
        Xs, y_dur_s, y_risk, test_size=0.2, random_state=42, stratify=y_risk
    )

    model = build_model()
    model.summary()

    early = keras.callbacks.EarlyStopping(
        monitor="val_loss", patience=10, restore_best_weights=True
    )

    model.fit(
        X_tr,
        {"duracion": ydur_tr, "riesgo": yr_tr},
        validation_data=(X_val, {"duracion": ydur_val, "riesgo": yr_val}),
        epochs=200,
        batch_size=64,
        callbacks=[early],
        verbose=2,
    )

    # Evaluación final
    resultados = model.evaluate(
        X_val, {"duracion": ydur_val, "riesgo": yr_val}, verbose=0, return_dict=True
    )
    acc = resultados.get("riesgo_accuracy", resultados.get("compile_metrics", 0))
    print("\n-- Evaluacion en validacion --")
    for k, v in resultados.items():
        print(f"   {k}: {v:.4f}")

    # Guardado
    os.makedirs(ML_DIR, exist_ok=True)
    model.save(MODEL_PATH)
    joblib.dump(
        {
            "x_scaler": x_scaler,
            "y_scaler": y_scaler,
            "feature_names": FEATURE_NAMES,
            "val_accuracy": float(acc) if isinstance(acc, (int, float)) else None,
            "n_train": int(len(X_tr)),
            "n_total": int(len(X)),
        },
        SCALERS_PATH,
    )
    print(f"\nOK - modelo -> {MODEL_PATH}")
    print(f"OK - scalers -> {SCALERS_PATH}")
    if isinstance(acc, (int, float)):
        print(f"val_riesgo_accuracy ~ {acc:.3f}  (meta > 0.75)")


if __name__ == "__main__":
    main()
