"""
Gestor de conexiones a SQLite.

Ruta: src/infrastructure/database/connection.py

Estrategia: una conexión por unidad de trabajo. Cada operación abre su
conexión, la usa y la cierra, siempre a través de un context manager.
En SQLite abrir una conexión local es muy barato, y así evitamos
conexiones "olvidadas" que mantengan bloqueado el archivo.

Uso típico desde un repositorio:

    with db.transaction() as conn:      # Escrituras (todo o nada)
        conn.execute("INSERT ...", params)

    with db.connection() as conn:       # Lecturas
        filas = conn.execute("SELECT ...").fetchall()
"""

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from src.config import settings
from src.infrastructure.database.exceptions import (
    DatabaseError,
    DatabaseIntegrityError,
    DatabaseLockedError,
    SchemaInitializationError,
)

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Punto único de acceso a la base de datos SQLite."""

    def __init__(
        self,
        db_path: Path,
        timeout: float = settings.DB_TIMEOUT_SECONDS,
    ) -> None:
        """
        Args:
            db_path: Ruta del archivo .db (se crea si no existe).
            timeout: Segundos de espera ante un bloqueo antes de fallar.
        """
        self._db_path = db_path
        self._timeout = timeout

    @property
    def db_path(self) -> Path:
        """Ruta del archivo de base de datos."""
        return self._db_path

    # ------------------------------------------------------------------ #
    # API pública
    # ------------------------------------------------------------------ #

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """
        Abre una transacción de escritura atómica.

        - BEGIN IMMEDIATE reserva el permiso de escritura desde el inicio,
          evitando el error "database is locked" a mitad de la operación.
        - Si todo sale bien: COMMIT. Si algo falla: ROLLBACK y se relanza.
        - La conexión se cierra siempre, pase lo que pase.
        """
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            yield conn
            conn.execute("COMMIT;")
        except sqlite3.Error as exc:
            self._rollback_quietly(conn)
            raise self._translate_error(exc) from exc
        except Exception:
            # Errores de negocio lanzados dentro del bloque "with":
            # se deshace lo escrito y se propagan sin modificarlos.
            self._rollback_quietly(conn)
            raise
        finally:
            conn.close()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Abre una conexión para lecturas (SELECT), sin transacción explícita."""
        conn = self._connect()
        try:
            yield conn
        except sqlite3.Error as exc:
            raise self._translate_error(exc) from exc
        finally:
            conn.close()

    def initialize_schema(self, schema_path: Path) -> None:
        """
        Crea las tablas si la base de datos es nueva.

        Usa PRAGMA user_version como "número de versión" del esquema:
        0 = base vacía; igual a SCHEMA_VERSION = al día; otro = requiere migración.

        Args:
            schema_path: Ruta del archivo schema.sql.

        Raises:
            SchemaInitializationError: Si el script no existe o falla.
        """
        try:
            script = schema_path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.exception("No se encontró el archivo de esquema: %s", schema_path)
            raise SchemaInitializationError(
                f"No se pudo leer el esquema en {schema_path}"
            ) from exc

        conn = self._connect()
        try:
            current_version: int = conn.execute("PRAGMA user_version;").fetchone()[0]

            if current_version == settings.SCHEMA_VERSION:
                logger.info("Esquema al día (versión %s).", current_version)
                return

            if current_version != 0:
                # Aquí se enganchará el sistema de migraciones en el futuro.
                raise SchemaInitializationError(
                    f"La base de datos está en la versión {current_version} y la "
                    f"aplicación espera la {settings.SCHEMA_VERSION}. Se requiere migración."
                )

            # Todo el script, incluida la versión, dentro de UNA transacción:
            # o se crean todas las tablas, o ninguna.
            conn.executescript(
                "BEGIN IMMEDIATE;\n"
                f"{script}\n"
                f"PRAGMA user_version = {settings.SCHEMA_VERSION};\n"
                "COMMIT;"
            )
            logger.info(
                "Esquema creado (versión %s) en %s", settings.SCHEMA_VERSION, self._db_path
            )
        except sqlite3.Error as exc:
            self._rollback_quietly(conn)
            logger.exception("Falló la creación del esquema.")
            raise SchemaInitializationError(f"No se pudo crear el esquema: {exc}") from exc
        finally:
            conn.close()

    # ------------------------------------------------------------------ #
    # Métodos internos
    # ------------------------------------------------------------------ #

    def _connect(self) -> sqlite3.Connection:
        """Crea y configura una conexión nueva."""
        try:
            # isolation_level=None desactiva las transacciones implícitas de
            # Python: nosotros controlamos BEGIN/COMMIT de forma explícita.
            conn = sqlite3.connect(
                self._db_path, timeout=self._timeout, isolation_level=None
            )
        except sqlite3.Error as exc:
            logger.exception("No se pudo abrir la base de datos en %s", self._db_path)
            raise DatabaseError(f"No se pudo abrir la base de datos: {exc}") from exc

        try:
            conn.row_factory = sqlite3.Row  # Acceso por nombre: fila["marca"]
            # SQLite trae las llaves foráneas APAGADAS por defecto.
            conn.execute("PRAGMA foreign_keys = ON;")
            # WAL: permite leer mientras otro proceso escribe.
            conn.execute("PRAGMA journal_mode = WAL;")
            # NORMAL es seguro con WAL y bastante más rápido que FULL.
            conn.execute("PRAGMA synchronous = NORMAL;")
        except sqlite3.Error as exc:
            conn.close()
            logger.exception("No se pudo configurar la conexión.")
            raise self._translate_error(exc) from exc

        return conn

    @staticmethod
    def _rollback_quietly(conn: sqlite3.Connection) -> None:
        """Deshace la transacción activa sin ocultar el error original."""
        try:
            if conn.in_transaction:
                conn.execute("ROLLBACK;")
        except sqlite3.Error:
            logger.exception("Falló el ROLLBACK (el error original se relanza igual).")

    @staticmethod
    def _translate_error(exc: sqlite3.Error) -> DatabaseError:
        """Convierte un error de sqlite3 en una excepción propia y lo registra."""
        message = str(exc)

        if isinstance(exc, sqlite3.IntegrityError):
            # Nivel WARNING: suele ser un dato inválido, no una falla del sistema.
            logger.warning("Violación de integridad: %s", message)
            return DatabaseIntegrityError(message)

        if isinstance(exc, sqlite3.OperationalError) and (
            "locked" in message.lower() or "busy" in message.lower()
        ):
            logger.error("Base de datos bloqueada tras esperar el tiempo máximo: %s", message)
            return DatabaseLockedError(
                "La base de datos está ocupada. Cierre otras ventanas del programa "
                "e intente de nuevo."
            )

        logger.error("Error de base de datos: %s", message, exc_info=exc)
        return DatabaseError(message)
