"""Mide el scoring por lotes (vectorizado) del mismo modelo de la API.
Uso (con el .venv activo, desde cualquier carpeta):  python escalabilidad/bench_batch.py [N_clientes]
Escribe escalabilidad/resultados_lote.csv (junto al script)
"""
import sys, time, csv, warnings
from pathlib import Path
import pandas as pd, skops.io as sio
warnings.filterwarnings("ignore")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 400000
base = Path(__file__).resolve().parent.parent  # raiz del proyecto (este script vive en escalabilidad/)
salida = Path(__file__).resolve().parent
modelo = sio.load(base / "model" / "model.skops", trusted=False)
df = pd.read_csv(base / "monitoring" / "data" / "baseline_train.csv")
cols = ["gender","SeniorCitizen","Partner","Dependents","tenure","PhoneService","MultipleLines","InternetService","OnlineSecurity","OnlineBackup","DeviceProtection","TechSupport","StreamingTV","StreamingMovies","Contract","PaperlessBilling","PaymentMethod","MonthlyCharges","TotalCharges"]
X = df[cols]
modelo.predict_proba(X.iloc[:2000])  # calentamiento
filas = []
for chunk in (1000, 10000, 50000):
    big = pd.concat([X] * (-(-N // len(X))), ignore_index=True).iloc[:N]
    t = time.perf_counter()
    n_ok = 0
    for i in range(0, N, chunk):
        p = modelo.predict_proba(big.iloc[i:i + chunk])[:, 1]; n_ok += len(p)
    dt = time.perf_counter() - t
    filas.append(dict(clientes=n_ok, tam_bloque=chunk, segundos=round(dt, 2), filas_por_s=round(n_ok / dt), ms_por_fila=round(dt / n_ok * 1000, 4)))
    print(filas[-1], flush=True)
with open(salida / "resultados_lote.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(filas[0])); w.writeheader(); w.writerows(filas)
