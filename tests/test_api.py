"""Pruebas automatizadas (pytest). Ejecutar desde la raíz del repo:  pytest -v"""

import sys
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sklearn.metrics import precision_score, recall_score

# Configuración de rutas para importar módulos del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from casos import CASOS  # noqa: E402
from app.main import app, modelo, UMBRAL  # noqa: E402

# Instancia del cliente de pruebas para FastAPI y ruta del dataset de prueba
client = TestClient(app)
PATH_DATASET_PRUEBA = Path(__file__).parent / "data" / "conjunto_prueba_act6.csv"


def test_health():
    # Verifica que el endpoint de salud responda correctamente
    response = client.get("/health")
    
    assert response.status_code == 200
    assert response.json()["estado"] == "ok"


def test_frontend_html():
    # Verifica que la ruta raíz cargue el frontend HTML adecuadamente
    response = client.get("/")
    
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "/predict" in response.text


@pytest.mark.parametrize(
    "cid, tipo, desc, payload, status_esperado, nivel_esperado",
    CASOS,
    ids=[caso[0] for caso in CASOS]
)
def test_casos(cid, tipo, desc, payload, status_esperado, nivel_esperado):
    # Ejecuta los casos de prueba (funcionales, extremos e inválidos).
    response = client.post("/predict", json=payload)
    
    # Validar que el código de estado HTTP coincida con lo esperado
    assert response.status_code == status_esperado

    # Validaciones adicionales si fue exitosa (HTTP 200)
    if status_esperado == 200:
        datos_respuesta = response.json()
        
        # Comprobar que la probabilidad esté en el rango válido [0.0, 1.0]
        probabilidad = datos_respuesta["probabilidad_churn"]
        assert 0.0 <= probabilidad <= 1.0
        
        # Comprobar que la predicción binaria coincida con el umbral configurado
        prediccion_esperada = int(probabilidad >= UMBRAL)
        assert datos_respuesta["prediccion"] == prediccion_esperada
        
        # Comprobar el nivel de riesgo si está especificado en el caso
        if nivel_esperado is not None:
            assert datos_respuesta["nivel_riesgo"] == nivel_esperado


def test_paridad_con_modelo_directo():
    # Verifica que la API devuelva exactamente los mismos resultados que invocar el modelo de forma directa
    # Cargar las primeras 100 filas del conjunto de prueba (omitiendo IDs y etiquetas reales)
    df_prueba = pd.read_csv(PATH_DATASET_PRUEBA).drop(columns=["customerID", "Churn"]).head(100)
    
    # Obtener predicciones directas del modelo de Machine Learning
    probabilidades_modelo_directo = modelo.predict_proba(df_prueba)[:, 1]
    
    # Comparar con la respuesta obtenida a través de la API para cada registro
    for indice, fila in enumerate(df_prueba.to_dict("records")):
        respuesta_api = client.post("/predict", json=fila).json()
        probabilidad_api = respuesta_api["probabilidad_churn"]
        
        # La diferencia debe ser casi imperceptible (menor a 0.0001)
        assert abs(probabilidad_api - probabilidades_modelo_directo[indice]) < 1e-4


def test_metricas_iguales_a_actividad_6():
    # Verifica que sobre el conjunto de prueba completo (n=1,409) se mantengan las métricas de la Act. 6 (recall 0.874, precisión 0.457).
    df_prueba = pd.read_csv(PATH_DATASET_PRUEBA)
    valores_reales = df_prueba["Churn"].to_numpy()
    
    # Generar predicciones de la API para todo el dataset de prueba
    registros = df_prueba.drop(columns=["customerID", "Churn"]).to_dict("records")
    predicciones_api = [
        client.post("/predict", json=registro).json()["prediccion"]
        for registro in registros
    ]
    
    # Validar métricas con un redondeo de 3 decimales
    recall_calculado = recall_score(valores_reales, predicciones_api)
    precision_calculado = precision_score(valores_reales, predicciones_api)
    
    assert round(recall_calculado, 3) == 0.874
    assert round(precision_calculado, 3) == 0.457