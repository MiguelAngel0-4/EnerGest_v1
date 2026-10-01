"""
Configuración global de la aplicación.

Ruta: src/config/settings.py

Centraliza las constantes del sistema para que ningún valor "mágico"
quede disperso en el código. Si un parámetro cambia (nombre de la BD,
prefijo del consecutivo, tamaño de los logs), se modifica solo aquí.
"""

from typing import Final

# --- Identidad de la aplicación -------------------------------------------
APP_NAME: Final[str] = "Gestión de Plantas Eléctricas"
APP_SLUG: Final[str] = "GestionPlantas"  # Nombre sin espacios, usado en carpetas
APP_VERSION: Final[str] = "0.1.0"

# --- Base de datos ----------------------------------------------------------
DB_FILENAME: Final[str] = "gestion_plantas.db"

# Segundos que SQLite espera a que se libere un bloqueo antes de fallar.
DB_TIMEOUT_SECONDS: Final[float] = 10.0

# Versión del esquema. Se guarda en PRAGMA user_version y permitirá
# aplicar migraciones ordenadas en futuras versiones.
SCHEMA_VERSION: Final[int] = 1

# Ruta del script SQL relativa a la raíz del proyecto (o del .exe).
SCHEMA_RELATIVE_PATH: Final[str] = "src/infrastructure/database/schema.sql"

# --- Logs --------------------------------------------------------------------
LOG_FILENAME: Final[str] = "app.log"
LOG_MAX_BYTES: Final[int] = 1_048_576  # 1 MB por archivo
LOG_BACKUP_COUNT: Final[int] = 5  # Se conservan app.log.1 ... app.log.5

# --- Consecutivos --------------------------------------------------------------
# En la BD se guarda solo el entero; el formato visible se arma en la UI.
CONSECUTIVO_PREFIJO: Final[str] = "PE-"
CONSECUTIVO_DIGITOS: Final[int] = 3  # 7 -> "PE-007"
