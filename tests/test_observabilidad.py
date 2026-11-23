"""Pruebas de la instrumentación de la Actividad 8 (logs y trazas por solicitud)."""
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import observabilidad  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)

PAYLOAD = {
    "gender": "Female", "SeniorCitizen": "Yes", "Partner": "No", "Dependents": "No", "tenure": 8,
    "PhoneService": "Yes", "MultipleLines": "Yes", "InternetService": "Fiber optic",
    "OnlineSecurity": "No", "OnlineBackup": "No", "DeviceProtection": "No", "TechSupport": "Yes",
    "StreamingTV": "Yes", "StreamingMovies": "Yes", "Contract": "Month-to-month",
    "PaperlessBilling": "Yes", "PaymentMethod": "Credit card (automatic)",
    "MonthlyCharges": 100.15, "TotalCharges": 908.55,
}


def _leer(ruta):
    return [json.loads(x) for x in ruta.read_text(encoding="utf-8").splitlines()]


def test_predict_genera_log_y_trazas(tmp_path, monkeypatch):
    monkeypatch.setattr(observabilidad, "LOG_DIR", tmp_path)
    r = client.post("/predict", json=PAYLOAD, headers={"X-Request-Id": "CLIENTE-1"})
    assert r.status_code == 200

    evento = _leer(tmp_path / "api_requests.jsonl")[0]
    assert evento["status"] == 200 and evento["request_id"] == "CLIENTE-1"
    assert abs(evento["probability"] - r.json()["probabilidad_churn"]) < 1e-3
    assert evento["features"]["tenure"] == 8

    etapas = [t["stage"] for t in _leer(tmp_path / "api_traces.jsonl")]
    assert etapas == ["validation", "inference", "decision", "total"]


def test_solicitud_invalida_se_registra_como_4xx_sin_entrada(tmp_path, monkeypatch):
    monkeypatch.setattr(observabilidad, "LOG_DIR", tmp_path)
    r = client.post("/predict", json={**PAYLOAD, "tenure": -5})
    assert r.status_code == 422
    evento = _leer(tmp_path / "api_requests.jsonl")[0]
    assert evento["status"] == 422 and evento["level"] == "WARNING" and evento["features"] is None


def test_health_no_se_instrumenta(tmp_path, monkeypatch):
    monkeypatch.setattr(observabilidad, "LOG_DIR", tmp_path)
    assert client.get("/health").status_code == 200
    assert not (tmp_path / "api_requests.jsonl").exists()
