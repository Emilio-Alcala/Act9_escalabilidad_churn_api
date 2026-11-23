# Dockerfile

# Imagen base ligera; misma versión de Python con la que se entrenó el modelo (3.14)
FROM python:3.14-slim

# Evita que Python cree archivos .pyc y que el buffer de salida se almacene en memoria
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Define el directorio de trabajo dentro del contenedor
WORKDIR /app

# copiar y instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia el código, frontend y el modelo entrenado al contenedor
COPY app ./app
COPY model/model.skops ./model/model.skops

# Usuario sin privilegios (buena práctica de seguridad)
# Crea un usuario llamado 'appuser' y establece su directorio home
RUN useradd --create-home appuser

# Cambia al usuario 'appuser' para ejecutar la aplicación (no como root)
USER appuser

EXPOSE 8000

# Define un healthcheck para verificar que la aplicación esté funcionando correctamente
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

# define el comando por defecto para ejecutar la aplicación FastAPI usando Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
