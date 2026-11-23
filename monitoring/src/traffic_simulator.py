"""Paso 3b · Simula tráfico de producción: envía una ventana de clientes a POST /predict.

La API (con app/observabilidad.py) registra cada solicitud en monitoring/logs/.
Después monitor.py lee esos logs y calcula las métricas de la ventana.

Uso (con la API corriendo en otra terminal):
  python monitoring/src/traffic_simulator.py --window monitoring/data/windows/normal_1.csv
"""
import argparse
import json
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import requests

FEATURES = ["gender", "SeniorCitizen", "Partner", "Dependents", "tenure", "PhoneService",
            "MultipleLines", "InternetService", "OnlineSecurity", "OnlineBackup",
            "DeviceProtection", "TechSupport", "StreamingTV", "StreamingMovies", "Contract",
            "PaperlessBilling", "PaymentMethod", "MonthlyCharges", "TotalCharges"]


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--window", required=True, help="CSV de la ventana (monitoring/data/windows/*.csv)")
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--concurrency", type=int, default=2, help="Solicitudes simultáneas (2 = tráfico normal; 8 para el incidente de latencia)")
    ap.add_argument("--n", type=int, default=None, help="Enviar solo las primeras N filas (pruebas rápidas)")
    ap.add_argument("--timeout", type=float, default=30.0)
    return ap.parse_args()


def payload_de(fila: pd.Series) -> dict:
    d = {c: fila[c] for c in FEATURES}
    d["tenure"] = int(d["tenure"])
    d["MonthlyCharges"] = float(d["MonthlyCharges"])
    d["TotalCharges"] = float(d["TotalCharges"])
    return d


def main():
    a = parse_args()
    ventana = pd.read_csv(a.window)
    if a.n:
        ventana = ventana.head(a.n)
    url = a.url.rstrip("/") + "/predict"

    def enviar(fila):
        t = time.perf_counter()
        try:
            r = requests.post(url, json=payload_de(fila),
                              headers={"X-Request-Id": str(fila["customerID"])}, timeout=a.timeout)
            codigo = r.status_code
        except requests.RequestException:
            codigo = 0  # no hubo respuesta (servicio caído o timeout)
        return codigo, (time.perf_counter() - t) * 1000

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=a.concurrency) as pool:
        resultados = list(pool.map(enviar, [f for _, f in ventana.iterrows()]))
    dur = time.perf_counter() - t0

    codigos = pd.Series([c for c, _ in resultados]).value_counts().sort_index().to_dict()
    lat = np.array([l for _, l in resultados])
    print(f"Ventana: {Path(a.window).name} | enviadas: {len(resultados)} en {dur:.1f} s")
    print(f"Códigos HTTP: {codigos}")
    print(f"Latencia vista por el cliente: p50 = {np.percentile(lat, 50):.0f} ms | p95 = {np.percentile(lat, 95):.0f} ms")
    salida = Path(__file__).resolve().parents[1] / "outputs"
    salida.mkdir(exist_ok=True)
    with (salida / "incident_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now().isoformat(timespec="seconds"), "event": "traffic_window_sent",
                            "window": Path(a.window).name, "requests": len(resultados), "http_codes": codigos}) + "\n")
    print("Siguiente paso: python monitoring/src/monitor.py --window-label <nombre>")


if __name__ == "__main__":
    main()
