"""Pruebas contra el servicio EN EJECUCIÓN (contenedor o local).
Uso:   python tests/pruebas_api.py [URL_BASE]     (por defecto http://localhost:8000)
Genera docs/evidencias/resultados_pruebas.csv y resumen en consola.
"""
import csv
import sys
import time
from pathlib import Path
import requests

# Configurar el path para poder importar los casos de prueba
sys.path.insert(0, str(Path(__file__).resolve().parent))
from casos import CASOS

# Configuración de URLs y rutas de salida del reporte
DEFAULT_URL = "http://localhost:8000"
URL = (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL).rstrip("/")
SALIDA = Path(__file__).resolve().parents[1] / "docs" / "evidencias" / "resultados_pruebas.csv"

# Verificar el estado de salud del servicio antes de iniciar las pruebas
health_url = f"{URL}/health"
health_response = requests.get(health_url, timeout=10)
print(f"GET /health -> {health_response.json()}")

filas = []
casos_exitosos = 0

print("\nEjecutando casos de prueba...")
print("-" * 80)

# Iterar sobre cada caso de prueba definido
for cid, tipo, desc, payload, esperado, nivel in CASOS:
    # Medir el tiempo de latencia de la petición
    inicio_tiempo = time.perf_counter()
    
    response = requests.post(f"{URL}/predict", json=payload, timeout=10)
    
    fin_tiempo = time.perf_counter()
    latencia_ms = (fin_tiempo - inicio_tiempo) * 1000

    # Obtener la respuesta en JSON si el estado HTTP es 200 (éxito)
    datos_respuesta = response.json() if response.status_code == 200 else {}

    # Validar si el resultado cumple con lo esperado
    status_correcto = (response.status_code == esperado)
    nivel_correcto = (nivel is None) or (datos_respuesta.get("nivel_riesgo") == nivel)
    pasa = status_correcto and nivel_correcto

    if pasa:
        casos_exitosos += 1

    # Construir el registro para el reporte CSV
    filas.append({
        "id": cid,
        "tipo": tipo,
        "descripcion": desc,
        "http_esperado": esperado,
        "http_obtenido": response.status_code,
        "probabilidad": datos_respuesta.get("probabilidad_churn", ""),
        "nivel": datos_respuesta.get("nivel_riesgo", ""),
        "prediccion": datos_respuesta.get("prediccion", ""),
        "latencia_ms": round(latencia_ms, 1),
        "resultado": "PASA" if pasa else "FALLA"
    })

    # Preparar variables para la salida en consola
    prob_str = str(datos_respuesta.get('probabilidad_churn', '-'))
    nivel_str = str(datos_respuesta.get('nivel_riesgo', '-'))
    estado_str = "PASA" if pasa else "FALLA"

    # Mostrar el progreso de la prueba en la consola
    print(
        f"[{cid}] {tipo:<10} | "
        f"HTTP {response.status_code} | "
        f"Prob: {prob_str:<7} | "
        f"Nivel: {nivel_str:<6} | "
        f"{latencia_ms:6.1f} ms | "
        f"{estado_str}"
    )

print("-" * 80)

# Asegurar que el directorio de salida exista y guardar el archivo CSV
SALIDA.parent.mkdir(parents=True, exist_ok=True)

with open(SALIDA, "w", newline="", encoding="utf-8-sig") as archivo_csv:
    escritor = csv.DictWriter(archivo_csv, fieldnames=list(filas[0].keys()))
    escritor.writeheader()
    escritor.writerows(filas)

# Resumen final en consola
total_casos = len(CASOS)
print(f"\nResumen: {casos_exitosos}/{total_casos} casos aprobados.")
print(f"Reporte guardado en: {SALIDA}")

# Salir con código 0 si todo pasó, o 1 si hubo al menos un fallo
sys.exit(0 if casos_exitosos == total_casos else 1)
