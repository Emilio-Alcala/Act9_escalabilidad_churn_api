# Escalabilidad, FinOps y gobernanza – Actividad 9

Documentación del código y de los artefactos generados en la Actividad 9 (Temas 21 y 22) del proyecto de churn de **Sierra Móvil**, construido sobre la API de la Actividad 8.

- Curso: Gestión de Proyectos de Inteligencia Artificial (CC.MSCA2102FLE.102.202630)
- Alumno: Emilio Alcalá Aguirre · T07181723
- Maestro: Tania Judith Mendoza Torres

> Los datos son públicos (IBM Telco Customer Churn, Kaggle) y simulan a Sierra Móvil. Las mediciones se hicieron **localmente**; los costos y la capacidad en AWS son **estimaciones** con supuestos declarados en el Anexo técnico. El rediseño no se desplegó en AWS.

## 1. Contenido y estructura

Todo lo de esta actividad vive en el subfolder `escalabilidad/`, separado de la Fase II y la Actividad 8 (`app/`, `model/`, `monitoring/`, que no se modifican).

```
<raiz del proyecto>/
├── app/ model/ monitoring/ ...      (Fase II y Actividad 8)
├── docs/
│   └── PIA - Reporte_11_Actividad_09.docx
└── escalabilidad/
    ├── readme_escalabilidad.md
    ├── load_test.py
    ├── bench_batch.py
    ├── resultados_carga.csv
    ├── resultados_lote.csv
    ├── Anexo_tecnico_Actividad_09.xlsx
    ├── Diagrama_arquitectura_actual_vs_propuesta.png
    └── carga_logs/
        ├── api_traces.jsonl
        └── api_request.jsonl
```

| Archivo | Descripción |
|---|---|
| `load_test.py` | Prueba de carga de la API (req/s, p50/p95/p99, errores, CPU y RAM por nivel de concurrencia) |
| `bench_batch.py` | Benchmark del scoring por lotes vectorizado con el mismo modelo |
| `resultados_carga.csv` | Salida de `load_test.py` |
| `resultados_lote.csv` | Salida de `bench_batch.py` |
| `carga_logs/` | Logs JSONL (`api_traces`, `api_request`) que la API generó durante la prueba de carga: evidencia de la medición |
| `Anexo_tecnico_Actividad_09.xlsx` | Supuestos, desempeño, capacidad, costos, campañas, sensibilidad, fairness, riesgos y fuentes (fórmulas vivas) |
| `Diagrama_arquitectura_actual_vs_propuesta.png` | Arquitectura actual (A) y propuesta (B) |
| `PIA - Reporte_11_Actividad_09.docx` | Reporte técnico (en `docs/`) |

`bench_batch.py` lee `model/model.skops` y `monitoring/data/baseline_train.csv` y calcula la raíz del proyecto a partir de su propia ubicación, así que corre desde cualquier carpeta. `load_test.py` no lee archivos del proyecto.

## 2. Requisitos

- Python del `.venv` del proyecto (incluye `pandas`, `skops` y `scikit-learn`).
- `load_test.py` usa solo la biblioteca estándar; `psutil` es opcional y habilita la medición de CPU y RAM (`pip install psutil`).

## 3. `load_test.py` – prueba de carga

Envía solicitudes `POST /predict` con tres clientes de ejemplo que rotan, usando una conexión nueva por solicitud, durante N segundos por nivel de concurrencia.

```bash
# 1) Levantar la API (Docker o uvicorn) y obtener el PID del proceso si se quiere CPU/RAM
# 2) Ejecutar
python escalabilidad/load_test.py --url http://127.0.0.1:8000 --seconds 20 --levels 1,5,10,20 --pid <PID> --out escalabilidad/resultados_carga.csv
```

| Parámetro | Default | Significado |
|---|---|---|
| `--url` | `http://localhost:8000` | URL base de la API |
| `--seconds` | 20 | Duración por nivel |
| `--levels` | `1,5,10,20` | Clientes concurrentes por nivel |
| `--pid` | — | PID del proceso de la API (con `psutil`, mide CPU y RAM incluyendo hijos) |
| `--out` | `resultados_carga.csv` | CSV de salida (usar `escalabilidad/resultados_carga.csv` para dejarlo en el subfolder) |

Columnas medidas por nivel: req/s, p50, p95 y p99 (ms), porcentaje de errores y, con `--pid`, CPU y RAM del proceso.

**Notas de uso**
- En Windows usar `127.0.0.1` en lugar de `localhost`: la resolución a IPv6 puede añadir ~2 s de latencia y invalidar la medición.
- Verificar que no haya latencia inyectada del simulador de fallas de la Actividad 8 antes de medir.
- La latencia es del lado cliente (incluye conexión nueva); no es comparable con la del servidor registrada en los logs de la Actividad 8.
- Es una corrida única por nivel: hay ruido entre niveles. Repetir y promediar para conclusiones más firmes.

**Resultados obtenidos (laptop Intel Core Ultra 7 155H, 64 GB, un proceso uvicorn, 0% de errores)**

| Clientes | req/s | p50 (ms) | p95 (ms) | CPU (%) | RAM máx. (MB) | p95 < 200 ms |
|---|---|---|---|---|---|---|
| 1 | 25.2 | 39.4 | 54.6 | 42 | 229 | Sí |
| 5 | 59.6 | 84.7 | 116.3 | 108 | 238 | Sí |
| 10 | 65.1 | 167.9 | 219.5 | 113 | 244 | No |
| 20 | 99.3 | 198.1 | 234.3 | 119 | 255 | No |

Los logs `api_traces.jsonl` y `api_request.jsonl` de esa corrida se guardaron en `carga_logs/`. Con esto, el consumo es de ~17 ms de CPU por solicitud (mediana) y ~250 MB de RAM por proceso.

## 4. `bench_batch.py` – scoring por lotes

Carga el modelo (`sio.load(..., trusted=False)`) y puntúa `N` clientes (por defecto 400,000, replicando el conjunto de entrenamiento) con `predict_proba` en bloques de 1,000, 10,000 y 50,000 filas, tras un calentamiento.

```bash
python escalabilidad/bench_batch.py            # 400,000 clientes
python escalabilidad/bench_batch.py 2000000    # escenario 5x
```

Escribe `escalabilidad/resultados_lote.csv` (junto al script). Columnas: `clientes`, `tam_bloque`, `segundos`, `filas_por_s` y `ms_por_fila`.

**Resultado de referencia (400,000 clientes):** bloque de 1,000 = 2.75 s; 10,000 = 1.09 s; 50,000 = 0.95 s (≈ 421,700 filas/s). Frente a la API (59.6 a 99.3 req/s), el lote es entre ~4,200 y ~7,100 veces más rápido.

## 5. Anexo técnico (Excel)

Hojas, en orden: **Supuestos** (celdas de entrada), **Desempeño** (resultados de `load_test.py` y `bench_batch.py`), **Capacidad** (modelo de req/s por vCPU y vCPU requeridas por escenario), **Costos** (App Runner, Fargate, comparación con dimensionar para el pico), **Campañas** (costo anual de contactar con umbral 0.188 contra tope del 15%), **Sensibilidad** (factor de velocidad de vCPU 1.5 / 2 / 3), **Fairness**, **Riesgos** y **Fuentes**.

Las cifras se calculan con fórmulas a partir de la hoja Supuestos: para probar otro escenario basta editar esas celdas. Supuestos principales: factor 2× de lentitud de una vCPU t3 frente a la laptop, utilización objetivo del 60%, ventana de lote de 4 h, escenarios 1× / 5× / 20× (400 mil / 2 M / 8 M de clientes), precios de AWS consultados el 21 de noviembre de 2026 y tipo de cambio 18.47 MXN/USD.

## 6. Resultados clave

- **Escalabilidad:** el cuello de botella no es la API interactiva sino el lote mensual pasado por la API (3.2 h a 1×, 15.8 h a 5× y 63 h a 20× en una t3.small).
- **Rediseño:** API en AWS App Runner (0.5 vCPU / 1 GB, mínimo 2 y máximo 6 instancias, HTTPS y API key) más lote vectorizado en ECS Fargate programado con EventBridge; logs y artefactos en CloudWatch y S3.
- **Costo:** ≈ $57 USD al mes en los tres escenarios (8.4% del presupuesto de $12,500 MXN). Dimensionar para el pico 24×7 costaría $72, $288 y $1,153 USD.
- **FinOps:** el costo dominante son las campañas ($46 MXN por contacto): el tope del 15% evita $6.59 M MXN al año a 1×.
- **Fairness (1,409 clientes de prueba):** sin disparidad relevante por género; adultos mayores reciben 1.7× más contactos con umbral 0.188; clientes con dependientes tienen recall de 0.20 con el top 15%. Reentrenar sin `Partner` y `Dependents` mantiene el AUC (0.842 contra 0.841), pero no cierra la brecha.
- **Plan responsable:** etapas 0 Preparación, 1 Piloto (10%), 2 Operación 1×, 3 Crecimiento 5× y 4 Estrés 20×, con compuertas técnicas, de costo y de equidad, aprobación por rol y reversión mediante `respond.py`.

## 7. Limitaciones

1. Carga medida en laptop, una corrida de 20 s por nivel; el p95 de 110–150 ms en la nube es una estimación pendiente de prueba en App Runner.
2. El factor 2× de vCPU, la demanda interactiva y la ventana de 4 h son supuestos (con sensibilidad en el Anexo).
3. Los precios cambian; el costo excluye EBS, CloudWatch, S3 y transferencia (estimados en menos de $5 USD al mes).
4. Datos públicos, no de Sierra Móvil: las métricas de fairness deben repetirse con datos reales.
5. Grupos pequeños (adultos mayores, n = 222) tienen intervalos de confianza amplios.
6. El análisis legal (LFPDPPP) es orientación académica y requiere revisión profesional.

## 8. Marcos de referencia

NIST AI Risk Management Framework 1.0, ISO/IEC 42001:2023 (alineación conceptual, sin certificación) y LFPDPPP (versión vigente desde el 21 de marzo de 2025). Las referencias completas están en el reporte.

## 9. Integración con la Fase III

Puntos listos para automatizar: despliegue reproducible de la imagen, tarea de lote programada, registro de modelos y compuertas de aprobación por etapa.
