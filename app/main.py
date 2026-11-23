"""API de predicción de churn - Sierra Móvil (Fase II).

Backend FastAPI    -> carga el modelo final de la Actividad 6 (regresión logística) y expone:
  GET  /           -> frontend HTML (formulario)
  GET  /health     -> estado del servicio
  GET  /info       -> metadatos del modelo y supuestos de negocio
  POST /predict    -> predicción para un cliente (JSON)
"""
from pathlib import Path
from typing import Literal

import pandas as pd
import skops.io as sio
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import observabilidad  # Actividad 8: logs y trazas por solicitud

BASE = Path(__file__).resolve().parent
MODELO_RUTA = BASE.parent / "model" / "model.skops"

# Supuestos de negocio (Excel de la Fase I y Actividad 6)
UMBRAL = 0.188             # = COSTO_CONTACTO / BENEFICIO_VP
COSTO_CONTACTO = 46.00     # MXN por cliente contactado
BENEFICIO_VP = 244.80      # MXN: 1,440 x 0.20 x 0.85
VERSION_API = "1.0.0"

SiNo = Literal["Yes", "No"]

app = FastAPI(
    title="Sierra Móvil - API de predicción de churn",
    description="Servicio de inferencia (regresión logística, umbral 0.188 por costos).",
    version=VERSION_API,
)

# Actividad 8: mide cada POST /predict y escribe log + trazas (ver app/observabilidad.py)
app.middleware("http")(observabilidad.middleware_observabilidad)

# El modelo se carga una sola vez al arrancar el proceso.
# trusted=False (por defecto): el modelo rechaza el archivo si contiene tipos no confiables
modelo = sio.load(MODELO_RUTA, trusted=False)


class Cliente(BaseModel):
    # Entrada: las 19 variables con las que se entrenó el modelo.
    gender: Literal["Male", "Female"]
    SeniorCitizen: SiNo
    Partner: SiNo
    Dependents: SiNo
    tenure: int = Field(ge=0, le=100, description="Meses como cliente")
    PhoneService: SiNo
    MultipleLines: SiNo
    InternetService: Literal["DSL", "Fiber optic", "No"]
    OnlineSecurity: SiNo
    OnlineBackup: SiNo
    DeviceProtection: SiNo
    TechSupport: SiNo
    StreamingTV: SiNo
    StreamingMovies: SiNo
    Contract: Literal["Month-to-month", "One year", "Two year"]
    PaperlessBilling: SiNo
    PaymentMethod: Literal[ "Electronic check", 
                            "Mailed check",
                            "Bank transfer (automatic)", 
                            "Credit card (automatic)"  ]
    MonthlyCharges: float = Field(ge=0, le=1000, description="Cargo mensual (MXN)")
    TotalCharges: float = Field(ge=0, le=100000, description="Cargo acumulado (MXN)")

@app.get("/", include_in_schema=False)
def inicio():
    return FileResponse(BASE / "static" / "index.html")

@app.get("/health")
def health():
    return {"estado": "ok", "modelo_cargado": modelo is not None, "version_api": VERSION_API}


@app.get("/info")
def info():
    return {
        "modelo": "Regresión logística (Pipeline: escalado + one-hot + LogisticRegression C=10)",
        "origen": "Actividad 6 - Churn Telco / Sierra Móvil",
        "umbral": UMBRAL,
        "costo_contacto_mxn": COSTO_CONTACTO,
        "beneficio_esperado_por_vp_mxn": BENEFICIO_VP,
        "n_variables_entrada": len(Cliente.model_fields),
        "version_api": VERSION_API,
    }


@app.post("/predict")
def predict(cliente: Cliente, request: Request):
    marcas = observabilidad.Marcas(request)
    marcas.etapa("validation")          # desde que llegó la solicitud hasta validar la entrada

    df = pd.DataFrame([cliente.model_dump()])
    observabilidad.inyectar_latencia()  # falla simulada; no hace nada si INJECT_LATENCY_MS = 0
    prob = float(modelo.predict_proba(df)[0, 1])
    marcas.etapa("inference")

    contactar = prob >= UMBRAL
    valor = prob * BENEFICIO_VP - COSTO_CONTACTO  # beneficio esperado neto de contactar
    if prob >= 0.5:
        nivel = "Alto"
    elif contactar:
        nivel = "Medio"
    else:
        nivel = "Bajo"
    marcas.etapa("decision")
    marcas.guardar(features=cliente.model_dump(), probability=round(prob, 6),
                   prediction=int(contactar), model_version=VERSION_API)
    return {
        "probabilidad_churn": round(prob, 4),
        "umbral": UMBRAL,
        "prediccion": int(contactar),
        "nivel_riesgo": nivel,
        "accion_recomendada": "Contactar con oferta de retención" if contactar else "No contactar",
        "valor_esperado_contacto_mxn": round(valor, 2),
    }


app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
