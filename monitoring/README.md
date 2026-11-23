# Monitoreo y observabilidad · Sierra Móvil (Actividad 8)

Instrumenta la API de churn y calcula SLI/SLO, alertas con prioridad, control de ruido y evidencia en MLflow.

```text
traffic_simulator.py --POST /predict--> API (app/observabilidad.py) --> logs/api_requests.jsonl  (LOGS)
                                                                    --> logs/api_traces.jsonl    (TRAZAS por etapa)
monitor.py lee la última ventana -> métricas -> umbrales/SLO -> control de ruido -> alertas + runbook + acción
                                 -> outputs/*.json + MLflow
```

## Preparación (una vez, desde la raíz del repo, con el venv activo)
```powershell
python -m pip install -r requirements-monitoring.txt
# copia telco_churn_limpio.csv a monitoring\data\raw\
python monitoring\src\prepare_data.py
```

## Flujo normal
```powershell
# Terminal 1 (API)
python -m uvicorn app.main:app --port 8000
# Terminal 2
python monitoring\src\traffic_simulator.py --window monitoring\data\windows\normal_1.csv
python monitoring\src\monitor.py --window-label normal_1 --reset-history
```

## Archivos
| Archivo | Para qué sirve |
|---|---|
| `app/observabilidad.py` | Middleware + cronómetro por etapas + falla simulada (`INJECT_LATENCY_MS`, apagada por defecto) |
| `monitoring/config/monitoring_config.json` | SLO, umbrales (con su justificación), prioridad, runbook y acción por métrica |
| `monitoring/src/prepare_data.py` | Baseline (5,634 filas de entrenamiento), referencia del modelo y ventanas de tráfico |
| `monitoring/src/traffic_simulator.py` | Envía una ventana de 500 clientes a `/predict` |
| `monitoring/src/monitor.py` | Métricas, alertas, ruido, MLflow y evidencia en `monitoring/outputs/` |

## .gitignore (agregar)
```
monitoring/logs/*.jsonl
monitoring/mlflow.db
monitoring/mlruns/
```
