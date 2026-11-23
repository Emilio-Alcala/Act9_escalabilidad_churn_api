"""Configuración común de pytest: aísla las pruebas de los logs y de la falla simulada del monitoreo."""
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="monitor_pytest_")
os.environ.setdefault("MONITOR_LOG_DIR", _tmp)                                  # no escribir en los logs reales
os.environ.setdefault("MONITOR_CONTROL_FILE", os.path.join(_tmp, "sin_falla.json"))  # ignorar una falla inyectada
