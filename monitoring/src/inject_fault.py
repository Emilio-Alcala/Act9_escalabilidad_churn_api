"""Simula un incidente de servicio SIN reiniciar la API (para el incidente B: latencia alta).

Escribe monitoring/control/runtime_config.json, que app/observabilidad.py lee en cada solicitud.
Equivale a "un despliegue defectuoso agregó latencia a la inferencia".

  python monitoring/src/inject_fault.py --latency-ms 700   # provoca la falla
  python monitoring/src/inject_fault.py --clear            # la quita (rollback MANUAL)
  python monitoring/src/inject_fault.py --status           # muestra el estado actual
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "control" / "runtime_config.json"
INCIDENTES = ROOT / "outputs" / "incident_log.jsonl"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--latency-ms", type=float, help="Milisegundos de retraso inyectados en la inferencia")
    g.add_argument("--clear", action="store_true")
    g.add_argument("--status", action="store_true")
    a = ap.parse_args()

    if a.status:
        print(CONTROL.read_text(encoding="utf-8") if CONTROL.exists() else "Sin archivo de control: sin falla (0 ms)")
        return
    ms = 0.0 if a.clear else a.latency_ms
    CONTROL.parent.mkdir(parents=True, exist_ok=True)
    CONTROL.write_text(json.dumps({"inject_latency_ms": ms}, indent=2), encoding="utf-8")
    INCIDENTES.parent.mkdir(parents=True, exist_ok=True)
    with INCIDENTES.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now().isoformat(timespec="seconds"),
                            "event": "fault_cleared_manually" if a.clear else "fault_injected",
                            "inject_latency_ms": ms}) + "\n")
    print(f"Falla {'retirada' if a.clear else 'inyectada'}: inject_latency_ms = {ms:g}")


if __name__ == "__main__":
    main()
