"""
Resolución de rutas del sistema de archivos.

Ruta: src/shared/paths.py

Resuelve dos problemas distintos:

1. Recursos de solo lectura (schema.sql, íconos, estilos):
   en desarrollo están en la raíz del proyecto; dentro del .exe,
   PyInstaller los descomprime en una carpeta temporal (sys._MEIPASS).

2. Carpetas escribibles (base de datos, logs, respaldos):
   en modo portable viven junto al .exe. Si esa carpeta no permite
   escritura (por ejemplo, si alguien copió el programa en
   "Archivos de programa"), se usa %APPDATA% como respaldo.
"""

import os
import sys
from pathlib import Path

from src.config import settings


def is_frozen() -> bool:
    """Indica si la aplicación se ejecuta empaquetada como .exe (PyInstaller)."""
    return bool(getattr(sys, "frozen", False))


def get_project_root() -> Path:
    """Raíz del proyecto en desarrollo (src/shared/paths.py -> tres niveles arriba)."""
    return Path(__file__).resolve().parents[2]


def get_resource_path(relative_path: str) -> Path:
    """
    Devuelve la ruta absoluta de un recurso empaquetado de solo lectura.

    Args:
        relative_path: Ruta relativa a la raíz, ej. "resources/styles/theme.qss".
    """
    if is_frozen():
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = get_project_root()
    return base / relative_path


def get_app_base_dir() -> Path:
    """Carpeta base de la aplicación: la del .exe o la raíz del proyecto."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return get_project_root()


def _is_writable(directory: Path) -> bool:
    """Comprueba de forma real (creando un archivo de prueba) si se puede escribir."""
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def _get_fallback_base() -> Path:
    """Ubicación alternativa cuando la carpeta portable no es escribible."""
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home()
    return base / settings.APP_SLUG


def get_writable_dir(subfolder: str) -> Path:
    """
    Devuelve una carpeta escribible, priorizando el modo portable.

    Args:
        subfolder: Nombre de la subcarpeta, ej. "data" o "logs".
    """
    preferred = get_app_base_dir() / subfolder
    if _is_writable(preferred):
        return preferred

    fallback = _get_fallback_base() / subfolder
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def is_using_fallback_location() -> bool:
    """True si los datos NO están junto al ejecutable (útil para avisar en el log)."""
    return not _is_writable(get_app_base_dir() / "data")


def get_data_dir() -> Path:
    """Carpeta donde vive la base de datos."""
    return get_writable_dir("data")


def get_logs_dir() -> Path:
    """Carpeta donde se escriben los logs."""
    return get_writable_dir("logs")


def get_database_path() -> Path:
    """Ruta completa del archivo SQLite."""
    return get_data_dir() / settings.DB_FILENAME
