"""Prueba de carga corta para la API de churn (solo biblioteca estandar; psutil opcional).
Uso:  python load_test.py --url http://localhost:8000 --seconds 20 --levels 1,5,10,20 [--pid PID] [--out resultados_carga.csv]
Mide por nivel de concurrencia: req/s, p50/p95/p99 (ms), % errores y, si se da --pid y hay psutil, CPU/RAM del proceso.
"""
import argparse, csv, json, statistics, threading, time, urllib.request, urllib.error

MUESTRAS = [
 {"gender":"Male","SeniorCitizen":"No","Partner":"Yes","Dependents":"Yes","tenure":72,"PhoneService":"Yes","MultipleLines":"Yes","InternetService":"Fiber optic","OnlineSecurity":"Yes","OnlineBackup":"Yes","DeviceProtection":"Yes","TechSupport":"Yes","StreamingTV":"Yes","StreamingMovies":"Yes","Contract":"Two year","PaperlessBilling":"Yes","PaymentMethod":"Credit card (automatic)","MonthlyCharges":114.05,"TotalCharges":8468.2},
 {"gender":"Female","SeniorCitizen":"Yes","Partner":"No","Dependents":"No","tenure":8,"PhoneService":"Yes","MultipleLines":"Yes","InternetService":"Fiber optic","OnlineSecurity":"No","OnlineBackup":"No","DeviceProtection":"No","TechSupport":"Yes","StreamingTV":"Yes","StreamingMovies":"Yes","Contract":"Month-to-month","PaperlessBilling":"Yes","PaymentMethod":"Electronic check","MonthlyCharges":100.15,"TotalCharges":908.55},
 {"gender":"Female","SeniorCitizen":"No","Partner":"Yes","Dependents":"Yes","tenure":41,"PhoneService":"Yes","MultipleLines":"Yes","InternetService":"DSL","OnlineSecurity":"Yes","OnlineBackup":"Yes","DeviceProtection":"Yes","TechSupport":"No","StreamingTV":"Yes","StreamingMovies":"No","Contract":"One year","PaperlessBilling":"Yes","PaymentMethod":"Bank transfer (automatic)","MonthlyCharges":79.85,"TotalCharges":3320.75},
]
CUERPOS = [json.dumps(m).encode() for m in MUESTRAS]

def un_cliente(url, fin, lat, errs, i0):
    i = i0
    while time.perf_counter() < fin:
        req = urllib.request.Request(url + "/predict", data=CUERPOS[i % 3], headers={"Content-Type": "application/json"})
        t = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                r.read(); ok = r.status == 200
        except Exception:
            ok = False
        dt = (time.perf_counter() - t) * 1000
        (lat if ok else errs).append(dt)
        i += 1

def pct(v, p):
    v = sorted(v); return v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))] if v else float("nan")

def sondear(proc, stop, out):
    import psutil
    procs = [proc] + proc.children(recursive=True)
    for p in procs: p.cpu_percent(None)
    while not stop.is_set():
        time.sleep(1)
        try:
            procs = [proc] + proc.children(recursive=True)
            out["cpu"].append(sum(p.cpu_percent(None) for p in procs))
            out["rss"].append(sum(p.memory_info().rss for p in procs) / 1e6)
        except Exception:
            pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000"); ap.add_argument("--seconds", type=int, default=20)
    ap.add_argument("--levels", default="1,5,10,20"); ap.add_argument("--pid", type=int); ap.add_argument("--out", default="resultados_carga.csv")
    a = ap.parse_args()
    proc = None
    if a.pid:
        try:
            import psutil; proc = psutil.Process(a.pid)
        except Exception as e:
            print("Sin CPU/RAM (psutil no disponible o PID invalido):", e)
    for _ in range(30):  # calentamiento
        urllib.request.urlopen(urllib.request.Request(a.url + "/predict", data=CUERPOS[0], headers={"Content-Type": "application/json"})).read()
    filas = []
    for n in [int(x) for x in a.levels.split(",")]:
        lat, errs, stop, res = [], [], threading.Event(), {"cpu": [], "rss": []}
        fin = time.perf_counter() + a.seconds
        ths = [threading.Thread(target=un_cliente, args=(a.url, fin, lat, errs, k)) for k in range(n)]
        sp = threading.Thread(target=sondear, args=(proc, stop, res)) if proc else None
        t0 = time.perf_counter()
        if sp: sp.start()
        [t.start() for t in ths]; [t.join() for t in ths]
        dur = time.perf_counter() - t0; stop.set()
        if sp: sp.join()
        tot = len(lat) + len(errs)
        fila = dict(clientes=n, solicitudes=tot, req_s=round(tot / dur, 1), p50_ms=round(pct(lat, 50), 1), p95_ms=round(pct(lat, 95), 1),
                    p99_ms=round(pct(lat, 99), 1), media_ms=round(statistics.mean(lat), 1) if lat else None, errores_pct=round(100 * len(errs) / max(tot, 1), 2),
                    cpu_prom_pct=round(statistics.mean(res["cpu"]), 0) if res["cpu"] else "", cpu_max_pct=round(max(res["cpu"]), 0) if res["cpu"] else "",
                    ram_max_mb=round(max(res["rss"]), 0) if res["rss"] else "")
        filas.append(fila); print(fila, flush=True)
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0])); w.writeheader(); w.writerows(filas)
    print("Guardado:", a.out)

if __name__ == "__main__":
    main()
