# Sierra Móvil · API de predicción de churn

Servicio de inferencia contenerizado (FastAPI + Docker) que publica el modelo final de la Actividad 6 para decidir a qué clientes de **Sierra Móvil** (empresa ficticia de telecomunicaciones) conviene contactar con una oferta de retención.

**Fase II – Despliegue local y en la nube** · **Actividad 8 – Monitoreo y observabilidad** · **Actividad 9 – Escalabilidad, FinOps y gobernanza**.

## Contenido

1. [Resumen](#1-resumen)
2. [Arquitectura](#2-arquitectura)
3. [Estructura de carpetas y archivos](#3-estructura-de-carpetas-y-archivos)
4. [Instalación](#4-instalación)
5. [Build (imagen Docker)](#5-build-imagen-docker)
6. [Run (ejecución)](#6-run-ejecución)
7. [Pruebas](#7-pruebas)
8. [Documentación](#8-documentación)
9. [Monitoreo y observabilidad (Actividad 8)](#9-monitoreo-y-observabilidad-actividad-8)
10. [Escalabilidad, FinOps y gobernanza (Actividad 9)](#10-escalabilidad-finops-y-gobernanza-actividad-9)

---

## 1. Resumen

**Problema de negocio.** Sierra Móvil (con aprox. 400,000 clientes, contrato y prepago) pierde clientes por abandono (*churn*). 

Contactar a un cliente cuesta dinero, así que solo conviene hacerlo cuando la probabilidad de abandono justifica el costo. El modelo estima esa probabilidad y la API la convierte en una decisión (contactar o no), un nivel de riesgo y un valor esperado en MXN.

**Qué hace este repositorio.** Empaqueta el modelo entrenado en la Actividad 6 dentro de una API REST con un frontend web, lo contenieriza con Docker y documenta su validación y su despliegue en la nube.


**Regla de decisión.** 
- `prediccion = 1` si `probabilidad >= 0.188` (= costo de contacto $46 / beneficio esperado por verdadero positivo $244.80). 
   
- Nivel de riesgo: 
  - Bajo  (< 0.188)
  - Medio (0.188–0.50)
  - Alto  (≥ 0.50)

- Valor esperado = `p × 244.80 − 46` MXN.

Ejemplo de respuesta de `POST /predict`:
```json
{
  "probabilidad_churn": 0.7792,
  "umbral": 0.188,
  "prediccion": 1,
  "nivel_riesgo": "Alto",
  "accion_recomendada": "Contactar con oferta de retención",
  "valor_esperado_contacto_mxn": 144.75
}
```

### 1.1 El modelo y cómo fue entrenado (README de la Actividad 6)

> Esta subsección reproduce el README de la Actividad 6 (*Evaluación y validación de modelos*), proyecto donde se entrenó y evaluó el modelo que aquí se despliega. Las rutas de esa actividad (`datos/`, `fuentes/`, `evidencias/`) pertenecen a ese proyecto y no a este repositorio.

**Actividad 6 – Evaluación y validación de modelos.** el business case de la Fase I (supuestos del Excel `PIA - Sierra Movil ROI v2.xlsx`).

**Qué contiene el proyecto de la Actividad 6**

```
datos/datos_limp/telco_churn_limpio.csv    datos limpios de la Actividad 5
fuentes/evaluacion.ipynb                   notebook completo (ejecutado)
evidencias/                                tablas CSV y gráficas generadas por el notebook
requirements.txt
CHANGELOG.md
```

**Cómo reproducir el entrenamiento (Windows, PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd fuentes
jupyter notebook evaluacion.ipynb      # Run All, de arriba abajo
```

Se crea `mlflow.db` en la raíz del proyecto. Para ver los experimentos (en otra terminal, desde la raíz del proyecto):

```powershell
mlflow ui --backend-store-uri sqlite:///mlflow.db     # http://localhost:5000
```

Experimento de MLflow: `Churn_Telco_Eval_Actividad6`.

**Datos.** Dataset público *Telco Customer Churn* (IBM): 7,043 clientes, 19 variables de entrada y 26.5 % de abandono. Partición 80/20 estratificada con semilla 42 (5,634 clientes de entrenamiento y 1,409 de prueba).

**Modelo.** `Pipeline` de scikit-learn: escalado de 3 variables numéricas (`tenure`, `MonthlyCharges`, `TotalCharges`), *one-hot* de 16 variables categóricas y `LogisticRegression(C=10, max_iter=1000, random_state=42)`. Los hiperparámetros son los mejores resultados del *Grid Search* de la Actividad 5 (AUC, 5-fold). También se entrenó un Random Forest (200 árboles, profundidad 5) como modelo de comparación; el modelo final aprobado es la regresión logística.

**Supuestos de la Fase I (Excel)**

| Parámetro | Valor |
|---|---|
| Costo de contacto (C_FP) | $46 MXN |
| Margen por cliente retenido | 300 × 40 % × 12 = $1,440 MXN |
| Aceptación × atribución | 0.20 × 0.85 = 0.17 |
| Beneficio esperado por VP (C_FN) | $244.80 MXN |
| Umbral teórico | 46 / 244.80 = 0.188 |
| Capacidad de contacto | 15 % de la base |

**Decisiones principales**

- El umbral se elige con predicciones fuera de muestra del entrenamiento; la prueba se usa una sola vez.
- Validación cruzada estratificada 5×3, `Pipeline` con escalado y one-hot dentro de cada fold.
- Líneas base: Dummy, regla "contrato mes a mes" y "contactar a todos".
- Comparación: t pareada con corrección de Nadeau-Bengio y Wilcoxon.
- A/B simulado: 40,000 clientes (remuestreo del conjunto de prueba), Z de dos proporciones, 500 réplicas para estimar potencia.

**Resultado resumido (conjunto de prueba)**

- Modelo seleccionado: regresión logística.
- AUC 0.8415.
- Umbral 0.188: recall 0.874 y precisión 0.457.
- $33.44 netos por cliente frente a $25.96 con umbral 0.5.
- A/B con presupuesto igual: 1.04 % vs 1.77 % de retención; Z = 6.20, p < 0.001.

El archivo `model/model.skops` de este repositorio es el modelo de la regresión logística registrado en MLflow durante esa actividad, en formato skops (no ejecuta código arbitrario al cargarse, a diferencia de pickle).

### 1.2 Qué aporta la Fase II

- API REST y frontend HTML en un solo contenedor.
- Imagen Docker reproducible con versiones fijadas (las mismas del entrenamiento).
- 18 pruebas automatizadas y 14 casos contra el servicio en ejecución; la API reproduce el recall 0.874 y la precisión 0.457 de la Actividad 6.
- Manual de despliegue en la nube y documento de validación y pruebas.
- **Actividad 8:** observabilidad de la API (logs y trazas JSONL), métricas, SLO, alertas con runbooks y respuesta controlada ([sección 9](#9-monitoreo-y-observabilidad-actividad-8)).
- **Actividad 9:** prueba de carga, benchmark de lote, rediseño de arquitectura, análisis de costos, auditoría de fairness y plan de escalamiento ([sección 10](#10-escalabilidad-finops-y-gobernanza-actividad-9)).

---

## 2. Arquitectura

```
Navegador (HTML + JavaScript)
   │  GET /            -> formulario
   │  POST /predict    -> JSON con las 19 variables del cliente
   ▼
┌── Contenedor Docker (python:3.14-slim, puerto 8000) ───────────────┐
│  uvicorn -> FastAPI (app/main.py)                                  │
│     │  valida entradas (Pydantic) -> DataFrame                     │
│     ▼                                                              │
│  Pipeline scikit-learn (model/model.skops)                         │
│     escalado + one-hot + LogisticRegression (C=10)                 │
│     │  probabilidad  ->  ≥ 0.188 ?  ->  acción y valor esperado    │
└────────────────────────────────────────────────────────────────────┘
```

| Componente | Archivo | Función |
|---|---|---|
| Backend / API | `app/main.py` | Carga el modelo al iniciar, valida entradas y responde predicciones |
| Frontend | `app/static/index.html` | Formulario que consume `POST /predict` con `fetch` |
| Modelo | `model/model.skops` | Pipeline entrenado en la Actividad 6 |
| Contenedor | `Dockerfile`, `.dockerignore` | Imagen reproducible, con `HEALTHCHECK` |

**Endpoints**

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Frontend HTML |
| GET | `/health` | Estado del servicio |
| GET | `/info` | Metadatos del modelo, umbral y supuestos de negocio |
| POST | `/predict` | Predicción para un cliente (JSON con 19 variables) |
| GET | `/docs` | Swagger UI (documentación interactiva) |

**Versiones** (iguales a las del entrenamiento): Python 3.14 · scikit-learn 1.9.1 · numpy 2.5.4 · pandas 3.1.0 · skops 0.16.0 · FastAPI 0.162.0 · uvicorn 0.54.0.

---

## 3. Estructura de carpetas y archivos

```
sierra-movil-churn-api/
├── app/
│   ├── __init__.py
│   ├── main.py                       # API FastAPI (endpoints, validación, decisión por umbral)
│   ├── observabilidad.py             # Actividad 8: middleware de logs/trazas y falla simulada
│   └── static/
│       └── index.html                # Frontend: formulario que consume /predict
├── model/
│   ├── model.skops                   # Pipeline entrenado (regresión logística, Actividad 6)
│   └── input_example.json            # Ejemplo de entrada registrado en MLflow
├── tests/
│   ├── casos.py                      # Casos funcionales (F), extremos (E) e inválidos (I)
│   ├── conftest.py                   # Configuración de pytest
│   ├── test_api.py                   # Pruebas automatizadas con pytest de la API
│   ├── test_observabilidad.py        # Pruebas del middleware de observabilidad (Actividad 8)
│   ├── pruebas_api.py                # Casos contra el servicio en ejecución -> CSV de resultados
│   └── data/
│       └── conjunto_prueba_act6.csv  # 1,409 clientes del conjunto de prueba de la Actividad 6
├── monitoring/                       # Actividad 8 (ver sección 9)
│   ├── README.md                     # Guía corta del monitoreo
│   ├── config/monitoring_config.json # SLO, umbrales, prioridad, runbook y acción por métrica
│   ├── control/                      # runtime_config.json (falla simulada) y known_good_config.json (rollback)
│   ├── data/                         # raw/, baseline_train.csv, labels_delayed.csv, reference_stats.json, windows/
│   ├── logs/                         # api_requests.jsonl y api_traces.jsonl (no se versionan)
│   ├── outputs/                      # alertas, historial, bitácoras, dashboard.png, runs/
│   ├── runbooks/                     # RB-01 (drift y calidad), RB-02 (degradación del servicio)
│   ├── src/                          # prepare_data, traffic_simulator, monitor, dashboard, respond, inject_fault
│   └── evidencia/                    # Capturas de la Actividad 8
├── escalabilidad/                    # Actividad 9 (ver sección 10)
│   ├── readme_escalabilidad.md       # Documentación detallada de la actividad
│   ├── load_test.py                  # Prueba de carga de la API
│   ├── bench_batch.py                # Benchmark de scoring por lotes
│   ├── resultados_carga.csv
│   ├── resultados_lote.csv
│   ├── Anexo_tecnico_Actividad_09.xlsx
│   ├── Diagrama_arquitectura_actual_vs_propuesta.png
│   └── carga_logs/                   # JSONL generados durante la prueba de carga
├── docs/
│   ├── Manual_Despliegue_Nube.pdf    # Manual de despliegue en la nube
│   ├── Validacion_y_Pruebas.pdf      # Documento de validación y pruebas
│   ├── PIA - Reporte_11_Actividad_09.docx  # Reporte técnico de la Actividad 9
│   └── evidencias/                   # Capturas y resultados_pruebas.csv
├── Dockerfile                        # Imagen: python:3.14-slim, usuario sin privilegios, HEALTHCHECK
├── .dockerignore                     # Excluye tests, docs, .git y temporales de la imagen
├── .gitignore
├── requirements.txt                  # Dependencias de ejecución (para producción)
├── requirements-dev.txt              # Incluye requirements.txt + pytest, httpx, requests (para pruebas de desarrollo)
├── requirements-monitoring.txt       # Incluye requirements.txt + mlflow, matplotlib, requests, pytest, httpx (Actividad 8)
└── README.md
```

---

## 4. Instalación

Para ejecutar las pruebas o la API **sin Docker** (para usar solo Docker no hace falta este paso).

Requisitos: Python 3.14 (la misma versión del entrenamiento) y Git.

```powershell
git clone https://github.com/<tu_usuario>/sierra-movil-churn-api.git
cd sierra-movil-churn-api

python -m venv .venv
.venv\Scripts\Activate.ps1          # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt # ya incluye requirements.txt
```

Si PowerShell bloquea la activación y no tienes permisos de administrador, usa `Set-ExecutionPolicy -Scope Process Bypass` en esa sesión, o activa el entorno con `.venv\Scripts\activate.bat` desde CMD.

Para usar el contenedor se requiere Docker Desktop (Windows, con WSL 2) o Docker Engine (Linux).

---

## 5. Build (imagen Docker)

Desde la carpeta raíz del proyecto:

```bash
docker build -t sierra-movil-churn .
docker images sierra-movil-churn
```

Para versionar la imagen: `docker build -t sierra-movil-churn:1.0.0 .`

---

## 6. Run (ejecución)

**Con Docker**

```bash
docker run -d --name churn-api -p 8000:8000 sierra-movil-churn
docker ps                  # estado Up y, después de unos segundos, healthy
docker logs churn-api      # debe indicar: Uvicorn running on http://0.0.0.0:8000
```

- Frontend: <http://localhost:8000>
- Swagger UI: <http://localhost:8000/docs>
- Estado: <http://localhost:8000/health>

Si el puerto 8000 está ocupado, usar `-p 8001:8000` y abrir `http://localhost:8001`.

Detener y limpiar:

```bash
docker stop churn-api
docker rm churn-api
```

**Sin Docker (desarrollo)**, con el entorno virtual activo:

```bash
uvicorn app.main:app --reload --port 8000
```

**Ejemplo de consulta desde la terminal**

```powershell
Invoke-RestMethod http://localhost:8000/health
```

```bash
curl http://localhost:8000/health
```

---

## 7. Pruebas

Con el entorno virtual activo y el servicio en ejecución (contenedor o `uvicorn`):

```bash
pytest -v                                              # 18 pruebas automatizadas
python tests/pruebas_api.py http://localhost:8000      # 14 casos contra el servicio -> docs/evidencias/resultados_pruebas.csv
```

| Tipo | Casos | Qué verifica |
|---|---|---|
| Funcionales | F01–F03 | Predicciones para perfiles típicos (cliente fiel, en riesgo, intermedio) |
| Extremos | E01–E05 | Cliente nuevo, límites del dominio, perfil de máximo riesgo y entrada incoherente |
| Inválidos | I01–I06 | Rechazo con HTTP 422 de valores negativos, categorías inexistentes, campos faltantes, texto en campos numéricos, valores fuera de rango y cuerpo vacío |
| Paridad | 100 clientes | La API devuelve lo mismo que el modelo cargado directamente (diferencia < 0.0001) |
| Métricas | 1,409 clientes | Reproduce el recall 0.874 y la precisión 0.457 de la Actividad 6 con umbral 0.188 |

`pytest` no necesita el contenedor: usa el cliente de pruebas de FastAPI. `pruebas_api.py` sí requiere que el servicio esté en ejecución.

---

## 8. Documentación

| Documento | Ubicación |
|---|---|
| Manual de despliegue en la nube (arquitectura, requerimientos, contenerización, GitHub, estrategia y pasos de despliegue en PaaS, seguridad, operación) | [`docs/Manual_Despliegue_Nube.pdf`](docs/Manual_Despliegue_Nube.pdf) |
| Documento de validación y pruebas (casos funcionales y extremos, paridad con la Actividad 6, hallazgos y conclusiones) | [`docs/Validacion_y_Pruebas.pdf`](docs/Validacion_y_Pruebas.pdf) |
| Evidencias (capturas y resultados por caso) | [`docs/evidencias/`](docs/evidencias/) |

---

## 9. Monitoreo y observabilidad (Actividad 8)

Instrumenta la API y calcula métricas, SLO, alertas con prioridad, control de ruido y evidencia en MLflow. Guía corta en [`monitoring/README.md`](monitoring/README.md).

```text
traffic_simulator.py --POST /predict--> API (app/observabilidad.py) --> logs/api_requests.jsonl  (LOGS)
                                                                    --> logs/api_traces.jsonl    (TRAZAS por etapa)
monitor.py lee la última ventana -> métricas -> umbrales/SLO -> control de ruido -> alertas + runbook + acción
                                 -> outputs/*.json + MLflow
```

**Qué mide.** Latencia (p95), tasa de éxito y consumo del presupuesto de error, deriva de datos (PSI sobre `tenure`, `MonthlyCharges`, `TotalCharges`, `Contract`, `InternetService` y `PaymentMethod`), comportamiento del modelo y, cuando llegan las etiquetas, calidad (recall y precisión). Cada ventana es de 500 solicitudes.

**SLO.** p95 de latencia menor a 200 ms (warning a 200 ms, crítico a 500 ms) y tasa de éxito de al menos 95%. Los umbrales, su justificación, la prioridad (P1 a P3), el runbook y la acción de cada métrica están en `monitoring/config/monitoring_config.json`. Un warning solo alerta si persiste en varias ventanas (control de ruido).

**Preparación (una vez, desde la raíz, con el entorno virtual activo)**

```powershell
python -m pip install -r requirements-monitoring.txt
# copiar telco_churn_limpio.csv a monitoring\data\raw\
python monitoring\src\prepare_data.py
```

**Flujo normal**

```powershell
# Terminal 1: API
python -m uvicorn app.main:app --port 8000
# Terminal 2: tráfico, monitor y dashboard
python monitoring\src\traffic_simulator.py --window monitoring\data\windows\normal_1.csv
python monitoring\src\monitor.py --window-label normal_1 --reset-history
python monitoring\src\dashboard.py            # genera monitoring\outputs\dashboard.png
```

Para evaluar calidad con etiquetas tardías: `python monitoring\src\monitor.py --window-label normal_1 --labels monitoring\data\labels_delayed.csv`. Para ver las corridas: `mlflow ui --backend-store-uri sqlite:///monitoring/mlflow.db`.

**Incidentes y respuesta**

| Incidente | Cómo se provoca | Respuesta |
|---|---|---|
| A: deriva de datos | Ventana `drift_1.csv` con `traffic_simulator.py` | RB-01: `respond.py` pone el lote en cuarentena, limita los contactos al presupuesto de campaña y abre una solicitud de reentrenamiento (nunca despliega un modelo solo; requiere aprobación humana) |
| B: latencia alta | `python monitoring\src\inject_fault.py --latency-ms 700` | RB-02: rollback a `control/known_good_config.json`; la falla se quita con `inject_fault.py --clear` |

`respond.py` corre en modo simulación por defecto; solo aplica la respuesta con `--execute`.

| Archivo | Función |
|---|---|
| `app/observabilidad.py` | Middleware, cronómetro por etapas y falla simulada. Variables de entorno opcionales: `MONITOR_ENABLED=0` (apaga el registro), `MONITOR_LOG_DIR=<ruta>` (carpeta de los JSONL), `INJECT_LATENCY_MS=<ms>` (falla simulada, apagada por defecto) |
| `monitoring/src/prepare_data.py` | Baseline (5,634 filas de entrenamiento), referencia del modelo y ventanas de tráfico |
| `monitoring/src/traffic_simulator.py` | Envía una ventana de 500 clientes a `/predict` |
| `monitoring/src/monitor.py` | Métricas, alertas, control de ruido, MLflow y evidencia en `monitoring/outputs/` |
| `monitoring/src/dashboard.py` | Dashboard operativo en una imagen (`--last N` para las últimas N ventanas) |
| `monitoring/src/respond.py` | Respuesta controlada a alertas críticas (cuarentena, rollback) |
| `monitoring/src/inject_fault.py` | Inyecta o quita latencia sin reiniciar la API (`--latency-ms`, `--clear`, `--status`) |

---

## 10. Escalabilidad, FinOps y gobernanza (Actividad 9)

Analiza cómo escalar el sistema de forma sostenible y responsable: mide el desempeño, rediseña la arquitectura, estima costos, audita el sesgo del modelo y propone un plan por etapas. Documentación detallada: [`escalabilidad/readme_escalabilidad.md`](escalabilidad/readme_escalabilidad.md); reporte completo: `docs/PIA - Reporte_11_Actividad_09.docx`.

**Ejecución (con el entorno virtual activo, desde la raíz)**

```powershell
# Prueba de carga: con la API levantada (usar 127.0.0.1; en Windows "localhost" puede añadir latencia por IPv6)
python escalabilidad\load_test.py --url http://127.0.0.1:8000 --seconds 20 --levels 1,5,10,20 --pid <PID> --out escalabilidad\resultados_carga.csv

# Benchmark de scoring por lotes (400,000 clientes por defecto)
python escalabilidad\bench_batch.py
```

Para guardar los logs de la prueba en `escalabilidad/carga_logs/`, levantar la API con `MONITOR_LOG_DIR=escalabilidad/carga_logs`. `load_test.py` usa solo la biblioteca estándar (`psutil` es opcional y habilita CPU y RAM).

**Hallazgos principales**

- Con un proceso, la API cumple p95 < 200 ms hasta 5 clientes concurrentes (59.6 req/s) y lo rebasa con 10 (65.1 req/s y p95 de 219.5 ms). El tope medido es de unos 100 req/s, con ~17 ms de CPU por solicitud y ~250 MB de RAM por proceso.
- El cuello de botella no es la API interactiva sino puntuar toda la base a través de ella: 400,000 clientes toman unas 1.9 h en la laptop. El scoring vectorizado por lotes los procesa en menos de 3 s, entre ~4,200 y ~7,100 veces más rápido.
- Rediseño propuesto: AWS App Runner (0.5 vCPU y 1 GB, de 2 a 6 instancias, HTTPS y API key) para la API y una tarea programada en ECS Fargate para el lote, con logs y artefactos centralizados. Costo estimado de unos $57 USD al mes en los escenarios 1×, 5× y 20× (precios de noviembre de 2026, supuestos en el Anexo técnico).
- El costo dominante son las campañas ($46 MXN por contacto), no la nube: el tope de contactos del 15% evita $6.59 M MXN al año a 1× frente al umbral 0.188 sobre toda la base.
- Fairness (1,409 clientes de prueba): sin disparidad relevante por género; los adultos mayores reciben 1.7× más contactos con el umbral 0.188; con el top 15%, el recall de clientes con dependientes es 0.20. Retirar `Partner` y `Dependents` no cambia el AUC (0.842 contra 0.841), pero tampoco cierra la brecha.
- Plan de escalamiento por etapas con compuertas técnicas, de costo y de equidad: Preparación, Piloto (10%), Operación 1×, Crecimiento 5× y Estrés 20×, con reversión mediante `respond.py`.

**Alcance.** La carga se midió en una laptop (una corrida de 20 s por nivel); los costos y la capacidad en AWS son estimaciones y el rediseño no se desplegó en la nube. Los datos son públicos y simulan a Sierra Móvil.

## Limitaciones

- El modelo se entrenó con el dataset público IBM Telco; Sierra Móvil es una empresa ficticia.
- La API no valida la coherencia entre variables (por ejemplo, `tenure = 0` con `TotalCharges` alto).
- Sin autenticación ni HTTPS en la versión local; en producción iría detrás de un gateway o de un PaaS con HTTPS (el rediseño de la Actividad 9 propone HTTPS y API key).
- El monitoreo corre sobre tráfico simulado y la prueba de carga se midió solo en local; el rediseño de la Actividad 9 no se desplegó en AWS.
