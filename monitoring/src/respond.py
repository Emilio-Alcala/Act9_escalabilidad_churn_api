"""Respuesta automatizada a las alertas ACTIVAS del monitor (Actividad 8).

Lee outputs/monitoring_summary.json y ejecuta la acción que cada alerta crítica tiene en la config.
Por seguridad TODO corre en modo simulación (dry-run) a menos que agregues --execute.

Acciones y sus salvaguardas
---------------------------
cuarentena_de_lote_y_evaluar_reentrenamiento   (drift crítico, P2)
    - Pone la ventana en cuarentena y limita los contactos al presupuesto de campaña
      (= % de contactos de referencia), eligiendo a los clientes de mayor probabilidad.
      El resto NO se descarta: queda en espera de validación con etiquetas.
    - Abre UNA solicitud de reentrenamiento (máx. 1 abierta). Nunca despliega un modelo solo:
      requiere aprobación humana.
rollback_o_reinicio_de_servicio                (latencia / errores críticos, P1)
    - Restaura la última configuración conocida como buena (control/known_good_config.json).
    - Cooldown: si ya se hizo un rollback hace menos de N minutos y el problema sigue, NO repite:
      ESCALA a una persona (outputs/escalation.json).
investigar_y_vigilar_mas_seguido               (cualquier warning)
    - Solo notifica; nunca modifica el servicio.

Cada decisión (ejecutada, simulada o bloqueada) queda en outputs/response_log.jsonl y en MLflow.

Uso (desde la raíz del repo):
  python monitoring/src/respond.py               # simulación: muestra qué haría
  python monitoring/src/respond.py --execute     # aplica la respuesta
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT, LOGS, CONTROL, DATA = ROOT / "outputs", ROOT / "logs", ROOT / "control", ROOT / "data"
ACCION_DRIFT = "cuarentena_de_lote_y_evaluar_reentrenamiento"
ACCION_ROLLBACK = "rollback_o_reinicio_de_servicio"
ACCION_AVISO = "investigar_y_vigilar_mas_seguido"


def leer_json(path: Path, defecto=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else defecto


def leer_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def registrar(entrada: dict) -> None:
    OUT.mkdir(exist_ok=True)
    entrada = {"ts": datetime.now().isoformat(timespec="seconds"), **entrada}
    with (OUT / "response_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(entrada, ensure_ascii=False) + "\n")


# ----------------------------------------------------------------------------- acciones
def accion_drift(resumen, cfg, ref, ejecutar):
    pol, etiqueta = cfg["response_policy"], resumen["window_label"]
    n_ventana = int(cfg["service"]["window_size"])
    eventos = [e for e in leer_jsonl(LOGS / "api_requests.jsonl") if e.get("event") == "predict_request"]
    ok = [e for e in eventos[-n_ventana:] if e["status"] == 200 and e.get("probability") is not None]
    n = len(ok)
    presupuesto = ref["contact_rate"] if pol["contact_budget_pct"] == "reference" else float(pol["contact_budget_pct"])
    original = sum(e["prediction"] for e in ok)
    k = min(original, int(round(presupuesto * n)))
    ordenados = sorted(ok, key=lambda e: e["probability"], reverse=True)
    elegidos = {id(e) for e in ordenados[:k]}
    ev = lambda e: e["probability"] * pol["benefit_per_retained_mxn"] - pol["cost_per_contact_mxn"]  # noqa: E731
    ev_original = sum(ev(e) for e in ok if e["prediction"] == 1)
    ev_tope = sum(ev(e) for e in ordenados[:k])
    detalle = {
        "ventana": etiqueta, "clientes_en_ventana": n,
        "presupuesto_pct": round(presupuesto, 4),
        "contactos_sin_tope": original, "contactos_con_tope": k,
        "costo_contacto_evitado_mxn": round((original - k) * pol["cost_per_contact_mxn"], 2),
        "valor_esperado_en_espera_mxn": round(ev_original - ev_tope, 2),
        "nota": "Los clientes fuera del tope quedan en espera de validación con etiquetas; no se descartan.",
    }
    abiertas = [r for r in [leer_json(OUT / "retraining_request.json")] if r and r.get("status") == "open"]
    detalle["solicitud_reentrenamiento"] = ("ya existe una abierta (no se duplica)"
                                            if len(abiertas) >= pol["max_open_retraining_requests"] else "se abre una nueva")
    if ejecutar:
        carpeta = OUT / "quarantine"
        carpeta.mkdir(parents=True, exist_ok=True)
        with (carpeta / f"{etiqueta}_lista_contacto.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["request_id", "probability", "contactar_sin_tope", "contactar_con_tope"])
            for e in ordenados:
                w.writerow([e["request_id"], e["probability"], e["prediction"], int(id(e) in elegidos)])
        (carpeta / f"{etiqueta}_cuarentena.json").write_text(
            json.dumps({"estado": "en_cuarentena", "alertas": resumen["alerts"], **detalle},
                       indent=2, ensure_ascii=False), encoding="utf-8")
        if not abiertas:
            (OUT / "retraining_request.json").write_text(json.dumps({
                "status": "open", "requires_human_approval": True,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "reason": "data drift crítico", "window": etiqueta,
                "drift_by_feature": resumen.get("drift_by_feature"),
                "suggested_data": "baseline_train.csv + ventana en cuarentena con etiquetas cuando lleguen",
            }, indent=2, ensure_ascii=False), encoding="utf-8")
    return detalle, {"contactos_sin_tope": original, "contactos_con_tope": k,
                     "costo_contacto_evitado_mxn": detalle["costo_contacto_evitado_mxn"],
                     "valor_esperado_en_espera_mxn": detalle["valor_esperado_en_espera_mxn"]}


def accion_rollback(resumen, cfg, ejecutar, cooldown_min):
    previos = [r for r in leer_jsonl(OUT / "response_log.jsonl")
               if r.get("action") == ACCION_ROLLBACK and r.get("mode") == "executed" and r.get("result") == "applied"]
    if previos:
        ultimo = datetime.fromisoformat(previos[-1]["ts"])
        if datetime.now() - ultimo < timedelta(minutes=cooldown_min):
            return {"bloqueado": f"rollback ya aplicado hace menos de {cooldown_min} min y la alerta sigue activa",
                    "decision": "ESCALAR a responsable (el rollback no resolvió el problema)"}, {}, "blocked"
    actual = leer_json(CONTROL / "runtime_config.json", {"inject_latency_ms": 0})
    bueno = leer_json(CONTROL / "known_good_config.json", {"inject_latency_ms": 0})
    detalle = {"configuracion_actual": actual, "configuracion_restaurada": bueno,
               "siguiente_paso": "enviar una ventana nueva y correr monitor.py: debe volver a OK"}
    if ejecutar:
        CONTROL.mkdir(exist_ok=True)
        (CONTROL / "runtime_config.json").write_text(json.dumps(bueno, indent=2), encoding="utf-8")
        (OUT / "post_action_verification.json").write_text(json.dumps({
            "pending": True, "action": ACCION_ROLLBACK, "applied_at": datetime.now().isoformat(timespec="seconds"),
            "criterio": "latency_p95_ms < 200 y error_budget_burn_rate < 0.5 en la siguiente ventana"},
            indent=2, ensure_ascii=False), encoding="utf-8")
    return detalle, {"latencia_inyectada_antes_ms": float(actual.get("inject_latency_ms", 0))}, "applied"


# ----------------------------------------------------------------------------- principal
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--execute", action="store_true", help="Aplica la respuesta (sin esto solo simula)")
    ap.add_argument("--config", default=str(ROOT / "config" / "monitoring_config.json"))
    ap.add_argument("--cooldown-minutes", type=float, default=None, help="Sobrescribe el cooldown del rollback (pruebas)")
    ap.add_argument("--no-mlflow", action="store_true")
    a = ap.parse_args()

    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    ref = json.loads((DATA / "reference_stats.json").read_text(encoding="utf-8"))
    resumen = leer_json(OUT / "monitoring_summary.json")
    if not resumen:
        raise SystemExit("No hay monitoring_summary.json. Corre primero monitor.py.")
    modo = "executed" if a.execute else "dry-run"
    etiqueta = resumen["window_label"]
    cooldown = a.cooldown_minutes if a.cooldown_minutes is not None else cfg["response_policy"]["cooldown_minutes_rollback"]
    print(f"\n=== RESPUESTA · ventana '{etiqueta}' · estado {resumen['status'].upper()} · modo {modo} ===")

    if not resumen["alerts"]:
        print("Sin alertas activas: no hay nada que ejecutar.")
        registrar({"window": etiqueta, "mode": modo, "action": "ninguna", "result": "sin_alertas"})
        return

    acciones = {}
    for alerta in resumen["alerts"]:
        acciones.setdefault(alerta["action"], []).append(alerta)

    for accion, alertas in acciones.items():
        gravedad = "critical" if any(x["severity"] == "critical" for x in alertas) else "warning"
        disparo = ", ".join(x["metric"] for x in alertas)
        print(f"\n-> {accion}  (disparada por: {disparo}; {gravedad})")
        if gravedad != cfg["response_policy"]["auto_execute_severity"]:
            print("   Solo es un warning: se notifica y se vigila; no se modifica el servicio.")
            registrar({"window": etiqueta, "mode": modo, "action": accion, "trigger": disparo,
                       "result": "notified_only"})
            continue
        metricas = {}
        if accion == ACCION_DRIFT:
            detalle, metricas = accion_drift(resumen, cfg, ref, a.execute)
            resultado = "applied"
        elif accion == ACCION_ROLLBACK:
            detalle, metricas, resultado = accion_rollback(resumen, cfg, a.execute, cooldown)
            if resultado == "blocked":
                if a.execute:
                    (OUT / "escalation.json").write_text(json.dumps({
                        "priority": "P1", "window": etiqueta, "reason": detalle["bloqueado"],
                        "alerts": alertas, "created_at": datetime.now().isoformat(timespec="seconds")},
                        indent=2, ensure_ascii=False), encoding="utf-8")
        else:
            detalle, resultado = {"nota": "acción sin implementación automática"}, "not_implemented"
        for k, v in detalle.items():
            print(f"   {k}: {v}")
        if not a.execute:
            print("   (SIMULACIÓN: no se cambió nada. Usa --execute para aplicar.)")
        registrar({"window": etiqueta, "mode": modo, "action": accion, "trigger": disparo,
                   "result": resultado if a.execute else f"would_{resultado}", "details": detalle})

        if not a.no_mlflow and cfg["mlflow"].get("enabled"):
            try:
                import mlflow
                mlflow.set_tracking_uri(f"sqlite:///{(ROOT / 'mlflow.db').resolve().as_posix()}")
                mlflow.set_experiment(cfg["mlflow"]["experiment_name"])
                with mlflow.start_run(run_name=f"respond_{etiqueta}_{modo}"):
                    mlflow.log_params({"window_label": etiqueta, "action": accion, "mode": modo,
                                       "trigger": disparo[:250], "result": resultado})
                    for k, v in metricas.items():
                        mlflow.log_metric(k, v)
            except ImportError:
                pass
    print("\nRegistro de la decisión: monitoring/outputs/response_log.jsonl")


if __name__ == "__main__":
    main()
