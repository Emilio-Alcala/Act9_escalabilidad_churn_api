# Runbook RB-02 · Degradación del servicio (latencia alta o errores) de la API de churn

## 1. Señal que activa el runbook
- Métrica: `latency_p95_ms` y `error_budget_burn_rate` (tasa de errores 5xx ÷ 5% de error budget).
- Umbral: `latency_p95_ms` ≥ 500 ms (critical, **P1**) o ≥ 200 ms (warning **P3**, solo alerta si persiste 2 ventanas); `error_budget_burn_rate` ≥ 1.0 (critical, P1) o ≥ 0.5 (warning).
- SLO: el 95% de las predicciones responde en < 200 ms y el 95% de las solicitudes termina con éxito.

## 2. Impacto esperado
El front-end y los procesos que consultan `/predict` esperan demasiado o reciben errores: la campaña de retención se retrasa y, si el error budget se agota, el servicio incumple su SLO.

## 3. Diagnóstico inicial
1. **Ubicar la etapa lenta** con las trazas (dashboard, panel «p95 por etapa», o `stage_p95_ms` en `monitoring_summary.json`): validación, inferencia o decisión.
2. **Separar el tipo de problema:** latencia sin errores, errores 5xx, o solicitudes rechazadas 4xx (estas últimas no consumen error budget).
3. **Buscar un cambio reciente:** `monitoring/outputs/incident_log.jsonl` y `monitoring/control/runtime_config.json` muestran qué configuración se aplicó y cuándo.
4. **Confirmar que no es carga:** el número de solicitudes de la ventana (`n_requests`) es el habitual.

## 4. Acción principal
Automática, con `python monitoring\src\respond.py --execute`: **rollback** a la última configuración conocida como buena (`control/known_good_config.json`).
- **Salvaguarda (cooldown):** si ya se hizo un rollback hace menos de 30 minutos y la alerta sigue activa, no se repite: se **escala a una persona** (`outputs/escalation.json`, P1).
- Un warning nunca ejecuta cambios: solo notifica y se vigila más de cerca.

## 5. Validación de recuperación
Enviar una ventana nueva y correr `monitor.py`: `latency_p95_ms` < 200 ms y `error_budget_burn_rate` < 0.5, sostenido durante 2 ventanas. El estado debe volver a OK.

## 6. Evidencia a conservar
Dashboard antes/durante/después · `alerts.json` · `response_log.jsonl` · `incident_log.jsonl` (hora de la falla) · corridas de MLflow · `stage_p95_ms` que señala la etapa afectada.

## 7. Mejora posterior
Prueba de carga antes de cada despliegue; despliegue gradual (canary) con rollback automático; alertas por etapa de la traza; límite de tiempo (timeout) y escalamiento automático de instancias en la nube (Fase III).
