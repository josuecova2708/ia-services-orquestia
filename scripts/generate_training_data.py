"""
Generador de datos SINTÉTICOS de entrenamiento para el modelo predictivo BPM.

No se conecta a Mongo: produce filas abstractas y generalizables. Cada fila
tiene las 6 features canónicas + dos labels (duración real y si hubo demora).

El "secreto" que la red debe aprender está en `_duracion_real`: una regla
latente determinística + ruido gaussiano. Si el modelo entrena bien, debe
descubrir estas relaciones por sí solo:
  - Más carga del funcionario  → más lento
  - Fin de semana              → más lento
  - Horario nocturno           → más lento
  - Más reintentos             → más lento
  - Nodos históricamente lentos tardan más en absoluto

Uso:
    python scripts/generate_training_data.py
    python scripts/generate_training_data.py --n 8000

Salida: data/training_data.json
"""

import argparse
import json
import os
import random

# Permite importar app.ml.modelo_bpm aunque se ejecute desde scripts/
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.ml.modelo_bpm import UMBRAL_DEMORA  # noqa: E402

SEED = 42
# Duraciones históricas típicas (minutos) de distintos tipos de nodo/actividad.
# Mezcla nodos rápidos y lentos para que el modelo vea todo el rango.
DURACIONES_BASE = [15, 20, 30, 45, 60, 90, 120, 180, 240]


def _duracion_real(hora, dia_semana, carga, dur_hist, intentos, rnd):
    """Regla latente: cuánto tarda REALMENTE la tarea según las condiciones."""
    factor = 1.0
    factor *= 1.0 + 0.08 * carga                       # sobrecarga
    factor *= 1.6 if dia_semana >= 5 else 1.0          # fin de semana
    factor *= 1.4 if (hora < 7 or hora > 20) else 1.0  # fuera de horario
    factor *= 1.0 + 0.5 * intentos                     # reintentos / reproceso
    ruido = 1.0 + rnd.gauss(0, 0.15)                   # variabilidad natural
    return max(1.0, dur_hist * factor * max(0.3, ruido))


def generar(n: int) -> list[dict]:
    rnd = random.Random(SEED)
    filas = []
    for _ in range(n):
        hora = rnd.randint(0, 23)
        dia_semana = rnd.randint(0, 6)
        carga = _muestra_carga(rnd)
        dur_hist = rnd.choice(DURACIONES_BASE) * rnd.uniform(0.8, 1.2)
        intentos = _muestra_intentos(rnd)

        dur_real = _duracion_real(hora, dia_semana, carga, dur_hist, intentos, rnd)
        hubo_demora = 1 if dur_real > UMBRAL_DEMORA * dur_hist else 0

        filas.append({
            "hora_creacion": hora,
            "dia_semana": dia_semana,
            "es_fin_semana": 1 if dia_semana >= 5 else 0,
            "carga_funcionario": carga,
            "duracion_historica_avg": round(dur_hist, 2),
            "intentos": intentos,
            "duracion_real_minutos": round(dur_real, 2),
            "hubo_demora": hubo_demora,
        })
    return filas


def _muestra_carga(rnd):
    """Carga sesgada hacia valores bajos pero con cola larga (algunos saturados)."""
    return min(15, int(abs(rnd.gauss(0, 3.5))))


def _muestra_intentos(rnd):
    """La mayoría de tareas no se reprocesan; pocas tienen 1-3 reintentos."""
    r = rnd.random()
    if r < 0.70:
        return 0
    if r < 0.88:
        return 1
    if r < 0.97:
        return 2
    return 3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=6000, help="Número de registros a generar")
    args = parser.parse_args()

    filas = generar(args.n)

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "training_data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(filas, f, ensure_ascii=False)

    demoras = sum(r["hubo_demora"] for r in filas)
    print(f"OK - {len(filas)} registros -> {out_path}")
    print(f"   Demoras: {demoras} ({100 * demoras / len(filas):.1f}%)  |  "
          f"Sin demora: {len(filas) - demoras}")


if __name__ == "__main__":
    main()
