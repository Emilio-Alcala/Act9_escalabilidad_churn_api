"""Observabilidad de la API de Sierra Móvil (Actividad 8).

Convierte cada llamada a POST /predict en señales observables:
  - LOG   -> monitoring/logs/api_requests.jsonl : un evento por solicitud (estado, latencia, entrada, salida)
  - TRAZA -> monitoring/logs/api_traces.jsonl   : una línea por etapa (validación -> inferencia -> decisión)
  - MÉTRICAS: las calcula después monitoring/src/monitor.py a partir de estos archivos.

Variables de entorno (todas opcionales):
  MONITOR_ENABLED=0         apaga el registro (por defecto está encendido)
  MONITOR_LOG_DIR=<ruta>    carpeta de los archivos JSONL (por defecto monitoring/logs)
  INJECT_LATENCY_MS=<ms>    INYECCIÓN DE FALLA para simular el incidente de latencia (valor inicial).
                            Apagada por defecto (0). Solo se usa en la simulación de incidentes.
  monitoring/control/runtime_config.json  {"inject_latency_ms": <ms>} se lee en cada solicitud y
                            tiene prioridad sobre la variable de entorno. Lo escriben inject_fault.py
                            (provocar la falla) y respond.py (rollback automático).
"""
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LOG_DIR = Path(os.getenv("MONITOR_LOG_DIR", BASE / "monitoring" / "logs"))
ENABLED = os.getenv("MONITOR_ENABLED", "1") != "0"
INJECT_LATENCY_MS = float(os.getenv("INJECT_LATENCY_MS", "0"))
# Archivo de control en caliente: permite simular (y revertir) una falla SIN reiniciar la API.
CONTROL_FILE = Path(os.getenv("MONITOR_CONTROL_FILE", BASE / "monitoring" / "control" / "runtime_config.json"))

RUTA_PREDICT = "/predict"
_candado = threading.Lock()


def _escribir(nombre_archivo: str, lineas: list[dict]) -> None:
    """Agrega líneas JSON al archivo (seguro entre hilos)."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    texto = "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lineas)
    with _candado:
        with (LOG_DIR / nombre_archivo).open("a", encoding="utf-8") as f:
            f.write(texto)


def _latencia_configurada_ms() -> float:
    """Lee el archivo de control; si no existe o está dañado, usa la variable de entorno."""
    try:
        return float(json.loads(CONTROL_FILE.read_text(encoding="utf-8")).get("inject_latency_ms", 0))
    except (OSError, ValueError, AttributeError):
        return INJECT_LATENCY_MS


def inyectar_latencia() -> None:
    """Falla simulada: retrasa la inferencia. No hace nada si la latencia configurada es 0."""
    ms = _latencia_configurada_ms()
    if ms > 0:
        time.sleep(ms / 1000.0)


class Marcas:
    """Cronómetro por etapas dentro del endpoint. Cada .etapa() mide desde la marca anterior."""

    def __init__(self, request):
        self.obs = getattr(request.state, "obs", None)
        self.ultimo = self.obs["t0"] if self.obs else time.perf_counter()
        self.etapas: dict[str, float] = {}

    def etapa(self, nombre: str) -> None:
        ahora = time.perf_counter()
        self.etapas[f"{nombre}_ms"] = round((ahora - self.ultimo) * 1000, 3)
        self.ultimo = ahora

    def guardar(self, **datos) -> None:
        """Deja los datos del resultado para que el middleware los escriba al terminar."""
        if self.obs is not None:
            self.obs["etapas"] = self.etapas
            self.obs.update(datos)


async def middleware_observabilidad(request, call_next):
    """Mide cada POST /predict y escribe el log y las trazas. Solo instrumenta esa ruta."""
    if not ENABLED or request.url.path != RUTA_PREDICT:
        return await call_next(request)

    t0 = time.perf_counter()
    trace_id = uuid.uuid4().hex[:12]
    request.state.obs = {"t0": t0, "trace_id": trace_id}
    estado = 500
    try:
        respuesta = await call_next(request)
        estado = respuesta.status_code
        return respuesta
    finally:
        # Se ejecuta siempre: con respuesta normal, con error 4xx o con excepción (500).
        total_ms = round((time.perf_counter() - t0) * 1000, 3)
        obs = request.state.obs
        ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        etapas = obs.get("etapas", {})

        evento = {
            "ts": ts,
            "event": "predict_request",
            "level": "ERROR" if estado >= 500 else "WARNING" if estado >= 400 else "INFO",
            "trace_id": trace_id,
            "request_id": request.headers.get("x-request-id"),
            "status": estado,
            "latency_ms": total_ms,
            "model_version": obs.get("model_version"),
            "probability": obs.get("probability"),
            "prediction": obs.get("prediction"),
            "features": obs.get("features"),
        }
        trazas = [
            {"ts": ts, "trace_id": trace_id, "stage": nombre.removesuffix("_ms"),
             "duration_ms": valor, "status": "ok"}
            for nombre, valor in etapas.items()
        ]
        trazas.append({"ts": ts, "trace_id": trace_id, "stage": "total",
                       "duration_ms": total_ms, "status": "ok" if estado < 500 else "error"})
        try:
            _escribir("api_requests.jsonl", [evento])
            _escribir("api_traces.jsonl", trazas)
        except OSError:
            pass  # la observabilidad nunca debe tumbar la predicción
