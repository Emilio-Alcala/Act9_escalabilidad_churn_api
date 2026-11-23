"""Paso 3a · Prepara los datos de referencia y las ventanas de "tráfico de producción".

Qué genera (todo en monitoring/data/):
  baseline_train.csv      5,634 clientes con los que se entrenó el modelo (Actividad 6).
                          Es la referencia para detectar DATA DRIFT (cambio en las entradas).
  reference_stats.json    Comportamiento esperado del modelo con datos que NO vio al entrenar
                          (conjunto de prueba): % de clientes a contactar, probabilidad media,
                          recall, precisión, F1, AUC. Es la referencia de predicciones y calidad.
  windows/normal_{1,2,3}.csv   Ventanas de 500 clientes elegidos al azar (tráfico normal).
  windows/drift_1.csv          Ventana de 500 clientes con perfil distinto (campaña de captación).
  labels_delayed.csv      customerID + Churn real. En producción las etiquetas llegan semanas
                          después; el monitor las usa solo para calcular recall/F1 "tardíos".

Uso (desde la raíz del repo, con el venv activo):
  python monitoring/src/prepare_data.py
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import skops.io as sio
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]      # monitoring/
REPO = ROOT.parent
DATA = ROOT / "data"

FEATURES = ["gender", "SeniorCitizen", "Partner", "Dependents", "tenure", "PhoneService",
            "MultipleLines", "InternetService", "OnlineSecurity", "OnlineBackup",
            "DeviceProtection", "TechSupport", "StreamingTV", "StreamingMovies", "Contract",
            "PaperlessBilling", "PaymentMethod", "MonthlyCharges", "TotalCharges"]


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--full", default=str(DATA / "raw" / "telco_churn_limpio.csv"),
                    help="CSV completo ya limpio (Actividad 5): 7,043 filas")
    ap.add_argument("--test", default=str(REPO / "tests" / "data" / "conjunto_prueba_act6.csv"),
                    help="Conjunto de prueba de la Actividad 6: 1,409 filas")
    ap.add_argument("--model", default=str(REPO / "model" / "model.skops"))
    ap.add_argument("--threshold", type=float, default=0.188, help="Umbral de decisión de la Fase I")
    ap.add_argument("--window-size", type=int, default=500)
    ap.add_argument("--seed", type=int, default=42)
    return ap.parse_args()


def main():
    a = parse_args()
    full = pd.read_csv(a.full)
    test = pd.read_csv(a.test)
    (DATA / "windows").mkdir(parents=True, exist_ok=True)

    # 1) Baseline = todo lo que NO es conjunto de prueba (los datos de entrenamiento)
    train = full[~full["customerID"].isin(test["customerID"])].reset_index(drop=True)
    assert len(train) + len(test) == len(full), "El conjunto de prueba no está contenido en el CSV completo"
    train.to_csv(DATA / "baseline_train.csv", index=False)
    print(f"baseline_train.csv: {len(train)} filas | churn real = {train['Churn'].mean():.4f}")

    # 2) Comportamiento de referencia del modelo con datos no vistos
    modelo = sio.load(a.model, trusted=False)
    prob = modelo.predict_proba(test[FEATURES])[:, 1]
    pred = (prob >= a.threshold).astype(int)
    y = test["Churn"].astype(int)
    ref = {
        "n_reference": int(len(test)),
        "threshold": a.threshold,
        "contact_rate": float(pred.mean()),
        "mean_probability": float(prob.mean()),
        "recall": float(recall_score(y, pred)),
        "precision": float(precision_score(y, pred)),
        "f1": float(f1_score(y, pred)),
        "auc": float(roc_auc_score(y, prob)),
        "churn_rate": float(y.mean()),
    }
    (DATA / "reference_stats.json").write_text(json.dumps(ref, indent=2), encoding="utf-8")
    print("reference_stats.json:", {k: round(v, 4) if isinstance(v, float) else v for k, v in ref.items()})

    # 3) Ventanas de tráfico
    cols = ["customerID"] + FEATURES
    rng = np.random.default_rng(a.seed)
    for i in (1, 2, 3):
        idx = rng.choice(len(test), size=a.window_size, replace=False)
        test.iloc[idx][cols].to_csv(DATA / "windows" / f"normal_{i}.csv", index=False)

    # Ventana con drift: campaña de captación que atrae sobre todo clientes mes a mes,
    # con fibra óptica, cheque electrónico y poca antigüedad (perfil de mayor riesgo).
    peso = np.ones(len(test))
    peso *= np.where(test["Contract"] == "Month-to-month", 4.0, 1.0)
    peso *= np.where(test["InternetService"] == "Fiber optic", 3.0, 1.0)
    peso *= np.where(test["PaymentMethod"] == "Electronic check", 3.0, 1.0)
    peso *= np.where(test["tenure"] <= 12, 4.0, 1.0)
    idx = rng.choice(len(test), size=a.window_size, replace=False, p=peso / peso.sum())
    test.iloc[idx][cols].to_csv(DATA / "windows" / "drift_1.csv", index=False)

    # 4) Etiquetas "tardías"
    test[["customerID", "Churn"]].to_csv(DATA / "labels_delayed.csv", index=False)
    print(f"Ventanas de {a.window_size} clientes en {DATA / 'windows'}: normal_1..3, drift_1")


if __name__ == "__main__":
    main()
