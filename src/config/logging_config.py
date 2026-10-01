"""
Configuración del sistema de logs.

Ruta: src/config/logging_config.py

- Escribe en un archivo rotativo (app.log, máx. 1 MB x 5 copias).
- Muestra también en consola cuando existe una (en desarrollo).
- Captura cualquier excepción no controlada: en un .exe sin consola,
  un error que no quede en el log simplemente "desaparece".
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType

from src.config import settings
from src.shared.paths import get_logs_dir

LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.INFO) -> Path:
    """
    Configura el logger raíz de la aplicación. Debe llamarse una sola vez
    al inicio de main.py, antes de cualquier otra operación.

    Args:
        level: Nivel mínimo a registrar (logging.DEBUG en desarrollo).

    Returns:
        Ruta del archivo de log, útil para mostrarla al usuario si hay errores.
    """
    log_path = get_logs_dir() / settings.LOG_FILENAME
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()  # Evita duplicar líneas si se llama dos veces

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=settings.LOG_MAX_BYTES,
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding="utf-8",  # Necesario para tildes y "ñ" en Windows
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # En un .exe compilado con --windowed, sys.stderr es None:
    # intentar escribir en él provocaría un error al arrancar.
    if sys.stderr is not None:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    sys.excepthook = _log_uncaught_exception
    return log_path


def _log_uncaught_exception(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: TracebackType | None,
) -> None:
    """Registra en el log cualquier excepción que nadie haya capturado."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.getLogger("excepcion_no_controlada").critical(
        "Excepción no controlada", exc_info=(exc_type, exc_value, exc_traceback)
    )
