"""Paso 3c · Monitor de la API de churn de Sierra Móvil (Actividad 8).

Lee los LOGS y TRAZAS que escribe la API, toma la última ventana de solicitudes y:
  1. calcula MÉTRICAS (latencia, errores, error budget, drift, comportamiento del modelo, calidad),
  2. las compara con los SLO/umbrales de config/monitoring_config.json,
  3. aplica CONTROL DE RUIDO (un warning solo alerta si persiste en varias ventanas),
  4. asigna PRIORIDAD (P1/P2/P3) y el RUNBOOK y la ACCIÓN de cada alerta,
  5. guarda evidencia en outputs/ y registra la corrida en MLflow.

Uso (desde la raíz del repo, con el venv activo):
  python monitoring/src/monitor.py --window-label normal_1
  python monitoring/src/monitor.py --window-label drift_1
  python monitoring/src/monitor.py --window-label normal_1 --labels monitoring/data/labels_delayed.csv
"""
from __future__ import annotations

import argparse
import json
import time
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]      # monitoring/
DATA, LOGS, OUT = ROOT / "data", ROOT / "logs", ROOT / "outputs"
PRIORIDAD = {"P1": 1, "P2": 2, "P3": 3}
GRAVEDAD = {"ok": 0, "warning": 1, "critical": 2}


# ----------------------------------------------------------------------------- utilidades
def parse_args():
    ap = argparse.ArgumentParser(description="Monitor de la API de churn (Actividad 8).")
    ap.add_argument("--config", default=str(ROOT / "config" / "monitoring_config.json"))
    ap.add_argument("--baseline", default=str(DATA / "baseline_train.csv"))
    ap.add_argument("--reference", default=str(DATA / "reference_stats.json"))
    ap.add_argument("--requests-log", default=str(LOGS / "api_requests.jsonl"))
    ap.add_argument("--traces-log", default=str(LOGS / "api_traces.jsonl"))
    ap.add_argument("--labels", default=None, help="CSV customerID,Churn con las etiquetas que ya llegaron")
    ap.add_argument("--window-label", default="ventana", help="Nombre de esta ventana (para la evidencia)")
    ap.add_argument("--reset-history", action="store_true", help="Borra el historial de ventanas (empezar un experimento limpio)")
    ap.add_argument("--no-mlflow", action="store_true")
    return ap.parse_args()


def leer_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def escribir_traza(trace_id: str, etapa: str, inicio: float) -> None:
    """Traza del propio monitor (qué tanto tarda cada etapa de su pipeline)."""
    OUT.mkdir(parents=True, exist_ok=True)
    linea = {"trace_id": trace_id, "stage": etapa, "duration_ms": round((time.perf_counter() - inicio) * 1000, 3),
             "status": "ok", "timestamp": time.time()}
    with (OUT / "monitor_traces.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(linea) + "\n")


# ----------------------------------------------------------------------------- drift (PSI)
def _psi(exp_pct: np.ndarray, act_pct: np.ndarray) -> float:
    exp_pct = np.clip(exp_pct, 1e-6, None)
    act_pct = np.clip(act_pct, 1e-6, None)
    return float(np.sum((act_pct - exp_pct) * np.log(act_pct / exp_pct)))


def psi_numerico(base: pd.Series, actual: pd.Series, bins: int = 10) -> float:
    """PSI con cortes por deciles del baseline."""
    b = pd.to_numeric(base, errors="coerce").dropna().to_numpy()
    a = pd.to_numeric(actual, errors="coerce").dropna().to_numpy()
    if len(b) == 0 or len(a) == 0:
        return float("nan")
    cortes = np.unique(np.quantile(b, np.linspace(0, 1, bins + 1)))
    if len(cortes) < 3:
        return 0.0
    cortes[0], cortes[-1] = -np.inf, np.inf
    cb, _ = np.histogram(b, bins=cortes)
    ca, _ = np.histogram(a, bins=cortes)
    return _psi(cb / cb.sum(), ca / max(ca.sum(), 1))


def psi_categorico(base: pd.Series, actual: pd.Series) -> float:
    """PSI sobre la proporción de cada categoría (una categoría nueva dispara el PSI)."""
    cats = sorted(set(base.dropna().astype(str)) | set(actual.dropna().astype(str)))
    pb = base.astype(str).value_counts(normalize=True).reindex(cats, fill_value=0).to_numpy()
    pa = actual.astype(str).value_counts(normalize=True).reindex(cats, fill_value=0).to_numpy()
    return _psi(pb, pa)


# ----------------------------------------------------------------------------- alertas
def evaluar(valor: float, regla: dict) -> str:
    w, c = float(regla["warning"]), float(regla["critical"])
    if regla.get("direction", "max") == "max":
        return "critical" if valor >= c else "warning" if valor >= w else "ok"
    return "critical" if valor <= c else "warning" if valor <= w else "ok"


def ventanas_consecutivas(historial: list[dict], metrica: str, gravedad: str) -> int:
    """Cuenta esta ventana + las inmediatamente anteriores con gravedad igual o peor."""
    n = 1
    for corrida in reversed(historial):
        if GRAVEDAD[corrida["severities"].get(metrica, "ok")] >= GRAVEDAD[gravedad]:
            n += 1
        else:
            break
    return n


# ----------------------------------------------------------------------------- principal
def main() -> None:
    a = parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    ref = json.loads(Path(a.reference).read_text(encoding="utf-8"))
    trace_id = uuid.uuid4().hex[:12]
    historial_path = OUT / "history.jsonl"
    if a.reset_history and historial_path.exists():
        historial_path.unlink()
    historial = leer_jsonl(historial_path)

    # 1) Cargar la ventana: las últimas N solicitudes a /predict
    t = time.perf_counter()
    n_ventana = int(cfg["service"]["window_size"])
    eventos = [e for e in leer_jsonl(Path(a.requests_log)) if e.get("event") == "predict_request"]
    if not eventos:
        raise SystemExit("No hay solicitudes en el log. Corre primero traffic_simulator.py con la API encendida.")
    ventana = eventos[-n_ventana:]
    ids = {e["trace_id"] for e in ventana}
    trazas = [x for x in leer_jsonl(Path(a.traces_log)) if x["trace_id"] in ids]
    baseline = pd.read_csv(a.baseline)
    escribir_traza(trace_id, "load_window", t)

    # 2) Calcular métricas
    t = time.perf_counter()
    m: dict[str, float] = {}
    lat = np.array([e["latency_ms"] for e in ventana])
    estados = np.array([e["status"] for e in ventana])
    m["n_requests"] = float(len(ventana))
    m["latency_p50_ms"] = float(np.percentile(lat, 50))
    m["latency_p95_ms"] = float(np.percentile(lat, 95))
    m["error_rate"] = float(np.mean(estados >= 500))
    m["invalid_request_rate"] = float(np.mean((estados >= 400) & (estados < 500)))
    permitido = max(1.0 - float(cfg["service"]["success_rate_target"]), 1e-9)
    m["service_success_rate"] = 1.0 - m["error_rate"]
    m["error_budget_burn_rate"] = m["error_rate"] / permitido
    m["error_budget_consumed_pct"] = 100.0 * m["error_budget_burn_rate"]

    ok = [e for e in ventana if e["status"] == 200 and e.get("features")]
    drift_por_variable: dict[str, float] = {}
    if ok:
        feats = pd.DataFrame([e["features"] for e in ok])
        m["contact_rate"] = float(np.mean([e["prediction"] for e in ok]))
        m["mean_probability"] = float(np.mean([e["probability"] for e in ok]))
        m["contact_rate_shift_pts"] = abs(m["contact_rate"] - ref["contact_rate"]) * 100
        m["mean_prob_shift"] = abs(m["mean_probability"] - ref["mean_probability"])
        for v in cfg["drift_features"]["numeric"]:
            drift_por_variable[v] = psi_numerico(baseline[v], feats[v])
        for v in cfg["drift_features"]["categorical"]:
            drift_por_variable[v] = psi_categorico(baseline[v], feats[v])
        m["drift_psi"] = float(max(drift_por_variable.values()))

        if a.labels:  # calidad real: solo con las etiquetas que ya llegaron
            from sklearn.metrics import f1_score, precision_score, recall_score
            etiquetas = pd.read_csv(a.labels).set_index("customerID")["Churn"]
            df = pd.DataFrame({"id": [e["request_id"] for e in ok], "pred": [e["prediction"] for e in ok]})
            df["y"] = df["id"].map(etiquetas)
            df = df.dropna(subset=["y"])
            if len(df) and df["y"].sum() > 0:
                m["n_labeled"] = float(len(df))
                m["recall"] = float(recall_score(df["y"], df["pred"]))
                m["precision"] = float(precision_score(df["y"], df["pred"], zero_division=0))
                m["f1"] = float(f1_score(df["y"], df["pred"], zero_division=0))

    etapas_p95 = {}
    if trazas:
        td = pd.DataFrame(trazas)
        etapas_p95 = {k: round(float(v), 3) for k, v in td.groupby("stage")["duration_ms"].quantile(0.95).items()}
    escribir_traza(trace_id, "compute_metrics", t)

    # 3) Evaluar umbrales + control de ruido + prioridad
    t = time.perf_counter()
    persist = cfg["noise_control"]["persistence_windows"]
    activas, suprimidas, severidades = [], [], {}
    for nombre, regla in cfg["thresholds"].items():
        if nombre not in m or not np.isfinite(m[nombre]):
            continue
        sev = evaluar(m[nombre], regla)
        severidades[nombre] = sev
        if sev == "ok":
            continue
        n_cons = ventanas_consecutivas(historial, nombre, sev)
        alerta = {
            "metric": nombre, "value": round(m[nombre], 4), "severity": sev,
            "priority": regla["priority"][sev],
            "warning_threshold": regla["warning"], "critical_threshold": regla["critical"],
            "direction": regla.get("direction", "max"),
            "consecutive_windows": n_cons, "required_windows": persist[sev],
            "runbook": regla["runbook"],
            "action": regla["action"] if sev == "critical" else "investigar_y_vigilar_mas_seguido",
        }
        if n_cons >= persist[sev]:
            activas.append(alerta)
        else:
            suprimidas.append({**alerta, "reason": f"ruido: {n_cons}/{persist[sev]} ventanas consecutivas"})
    activas.sort(key=lambda x: (PRIORIDAD[x["priority"]], -GRAVEDAD[x["severity"]]))
    # Agrupar alertas que comparten runbook en un solo incidente (menos ruido para quien responde)
    incidentes: dict[str, dict] = {}
    for x in activas:
        inc = incidentes.setdefault(x["runbook"], {"runbook": x["runbook"], "priority": x["priority"],
                                                   "action": x["action"], "metrics": []})
        inc["metrics"].append(x["metric"])
    estado = ("critical" if any(x["severity"] == "critical" for x in activas)
              else "warning" if activas else "ok")
    accion = (activas[0]["action"] if activas
              else "vigilar_siguiente_ventana" if suprimidas else "continuar_monitoreo")
    escribir_traza(trace_id, "evaluate_alerts", t)

    # 4) Evidencia
    resumen = {
        "project_name": cfg["project_name"], "window_label": a.window_label, "trace_id": trace_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": estado, "recommended_action": accion,
        "metrics": {k: round(v, 4) for k, v in m.items()},
        "drift_by_feature": {k: round(v, 4) for k, v in drift_por_variable.items()},
        "stage_p95_ms": etapas_p95,
        "incidents": list(incidentes.values()),
        "alerts": activas, "suppressed_alerts": suprimidas,
    }
    texto = json.dumps(resumen, indent=2, ensure_ascii=False)
    (OUT / "monitoring_summary.json").write_text(texto, encoding="utf-8")
    (OUT / "alerts.json").write_text(json.dumps(activas, indent=2, ensure_ascii=False), encoding="utf-8")
    carpeta = OUT / "runs"
    carpeta.mkdir(exist_ok=True)
    (carpeta / f"{a.window_label}_{datetime.now():%Y%m%d_%H%M%S}.json").write_text(texto, encoding="utf-8")
    with (OUT / "monitoring_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now().isoformat(timespec="seconds"), "event": "monitoring_run", "window_label": a.window_label, "status": estado,
                            "alerts": len(activas), "suppressed": len(suprimidas)}) + "\n")
    with historial_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"label": a.window_label, "ts": resumen["generated_at"], "severities": severidades}) + "\n")

    # 5) MLflow
    if cfg["mlflow"].get("enabled") and not a.no_mlflow:
        try:
            import mlflow
            mlflow.set_tracking_uri(f"sqlite:///{(ROOT / 'mlflow.db').resolve().as_posix()}")
            mlflow.set_experiment(cfg["mlflow"]["experiment_name"])
            with mlflow.start_run(run_name=f"monitor_{a.window_label}"):
                for k, v in m.items():
                    mlflow.log_metric(k, v)
                for k, v in drift_por_variable.items():
                    mlflow.log_metric(f"psi_{k}", v)
                for k, v in etapas_p95.items():
                    mlflow.log_metric(f"stage_p95_ms_{k}", v)
                mlflow.log_metric("alerts_active", len(activas))
                mlflow.log_metric("alerts_suppressed", len(suprimidas))
                mlflow.log_params({"window_label": a.window_label, "status": estado,
                                   "recommended_action": accion})
                mlflow.log_artifact(str(OUT / "monitoring_summary.json"), artifact_path="monitoring")
                mlflow.log_artifact(str(OUT / "alerts.json"), artifact_path="monitoring")
        except ImportError:
            print("ADVERTENCIA: MLflow no está instalado (pip install -r requirements-monitoring.txt).")

    # 6) Consola
    print(f"\n=== MONITOREO · ventana '{a.window_label}' · {len(ventana)} solicitudes ===")
    print(f"Estado: {estado.upper()}   |   acción recomendada: {accion}")
    for k in ["latency_p50_ms", "latency_p95_ms", "error_rate", "error_budget_burn_rate", "drift_psi",
              "contact_rate", "contact_rate_shift_pts", "mean_probability", "mean_prob_shift",
              "recall", "precision", "f1"]:
        if k in m:
            print(f"  {k:26s} {m[k]:10.4f}   [{severidades.get(k, '-')}]")
    if drift_por_variable:
        print("  PSI por variable:", {k: round(v, 3) for k, v in drift_por_variable.items()})
    print(f"  p95 por etapa (ms): {etapas_p95}")
    for x in activas:
        print(f"  ALERTA {x['priority']} [{x['severity'].upper()}] {x['metric']} = {x['value']} -> {x['runbook']}")
    for inc in incidentes.values():
        print(f"  INCIDENTE {inc['priority']}: {len(inc['metrics'])} alerta(s) -> un solo runbook {inc['runbook']}")
    for x in suprimidas:
        print(f"  (suprimida) {x['metric']} = {x['value']} [{x['severity']}] {x['reason']}")
    print(f"Evidencia: {OUT}")


if __name__ == "__main__":
    main()
