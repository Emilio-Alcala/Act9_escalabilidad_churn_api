# Sierra Móvil · API de predicción de churn

Servicio de inferencia contenerizado (FastAPI + Docker) que publica el modelo final de la Actividad 6 para decidir a qué clientes de **Sierra Móvil** (empresa ficticia de telecomunicaciones) conviene contactar con una oferta de retención.

**Fase II – Despliegue local y en la nube**.

## Contenido

1. [Resumen](#1-resumen)
2. [Arquitectura](#2-arquitectura)
3. [Estructura de carpetas y archivos](#3-estructura-de-carpetas-y-archivos)
4. [Instalación](#4-instalación)
5. [Build (imagen Docker)](#5-build-imagen-docker)
6. [Run (ejecución)](#6-run-ejecución)
7. [Pruebas](#7-pruebas)
8. [Documentación](#8-documentación)

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
│   └── static/
│       └── index.html                # Frontend: formulario que consume /predict
├── model/
│   ├── model.skops                   # Pipeline entrenado (regresión logística, Actividad 6)
│   └── input_example.json            # Ejemplo de entrada registrado en MLflow
├── tests/
│   ├── casos.py                      # Casos funcionales (F), extremos (E) e inválidos (I)
│   ├── test_api.py                   # Pruebas automatizadas con pytest (18)
│   ├── pruebas_api.py                # Casos contra el servicio en ejecución -> CSV de resultados
│   └── data/
│       └── conjunto_prueba_act6.csv  # 1,409 clientes del conjunto de prueba de la Actividad 6
├── docs/
│   ├── Manual_Despliegue_Nube.pdf    # Manual de despliegue en la nube
│   ├── Validacion_y_Pruebas.pdf      # Documento de validación y pruebas
│   └── evidencias/                   # Capturas y resultados_pruebas.csv
├── Dockerfile                        # Imagen: python:3.14-slim, usuario sin privilegios, HEALTHCHECK
├── .dockerignore                     # Excluye tests, docs, .git y temporales de la imagen
├── .gitignore
├── requirements.txt                  # Dependencias de ejecución (para producción)
├── requirements-dev.txt              # Incluye requirements.txt + pytest, httpx, requests (para pruebas de desarrollo)
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

## Limitaciones

- El modelo se entrenó con el dataset público IBM Telco; Sierra Móvil es una empresa ficticia.
- La API no valida la coherencia entre variables (por ejemplo, `tenure = 0` con `TotalCharges` alto).
- Sin autenticación ni HTTPS en la versión local; en producción iría detrás de un gateway o de un PaaS con HTTPS.
