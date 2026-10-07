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
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
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

    def initialize_schema(
        self,
        schema_path: Path,
        migrations_dir: Path | None = None,
        backup_dir: Path | None = None,
    ) -> None:
        """
        Deja la base de datos en la versión que espera la aplicación.

        Funciona como la Constitución y sus enmiendas:
        - schema.sql es el texto original (versión 1) y NUNCA se modifica.
        - Cada archivo NNN_descripcion.sql de migrations/ es una enmienda que
          lleva la base a la versión NNN. Se aplican en orden, una sola vez.
        Una base nueva y una existente terminan exactamente iguales.

        PRAGMA user_version guarda en qué versión está el archivo .db.

        Args:
            schema_path: Ruta del schema.sql (versión 1).
            migrations_dir: Carpeta de migraciones (por defecto, junto a schema.sql).
            backup_dir: Dónde guardar el respaldo previo a migrar
                        (por defecto, la subcarpeta "respaldos" junto al .db).

        Raises:
            SchemaInitializationError: Si falta un archivo, la base es más nueva
                que la aplicación o una migración falla (la base queda intacta).
        """
        migrations_dir = migrations_dir or schema_path.parent / "migrations"
        backup_dir = backup_dir or self._db_path.parent / "respaldos"
        objetivo = settings.SCHEMA_VERSION
        migraciones = self._listar_migraciones(migrations_dir)

        # Protección contra un olvido frecuente: agregar una migración y no
        # actualizar settings.SCHEMA_VERSION. Mejor fallar al iniciar con un
        # mensaje claro que funcionar con un esquema incompleto.
        if migraciones and max(migraciones) > objetivo:
            raise SchemaInitializationError(
                f"Existe la migración {max(migraciones):03d}, pero settings.SCHEMA_VERSION "
                f"es {objetivo}. Actualice SCHEMA_VERSION en src/config/settings.py."
            )

        actual = self._version_actual()
        if actual > objetivo:
            raise SchemaInitializationError(
                f"La base de datos está en la versión {actual} y esta aplicación solo "
                f"conoce hasta la {objetivo}. Use una versión más reciente del programa."
            )
        if actual == objetivo:
            logger.info("Esquema al día (versión %s).", actual)
            return

        if actual == 0:
            self._ejecutar_script(self._leer(schema_path), version_resultante=1)
            logger.info("Esquema base creado (versión 1) en %s", self._db_path)
            actual = 1
        else:
            # La base ya tiene información: se respalda ANTES de tocarla.
            respaldo = self.backup(backup_dir, etiqueta=f"v{actual}")
            logger.info("Respaldo previo a la migración guardado en %s", respaldo)

        for version in range(actual + 1, objetivo + 1):
            if version not in migraciones:
                raise SchemaInitializationError(
                    f"No se encontró la migración {version:03d} en {migrations_dir}."
                )
            self._ejecutar_script(self._leer(migraciones[version]), version_resultante=version)
            logger.info("Migración %s aplicada: %s", version, migraciones[version].name)

    def backup(self, carpeta: Path, etiqueta: str = "manual") -> Path:
        """
        Copia completa y consistente de la base de datos.

        Usa la API de respaldo nativa de SQLite, que copia de forma segura
        aunque la base esté en uso (copiar el archivo a mano podría dejar
        una copia corrupta si coincide con una escritura).

        Returns:
            Ruta del archivo de respaldo creado.
        """
        carpeta.mkdir(parents=True, exist_ok=True)
        marca_tiempo = datetime.now().strftime("%Y%m%d_%H%M%S")
        destino = carpeta / f"{self._db_path.stem}_{etiqueta}_{marca_tiempo}.db"
        origen = self._connect()
        try:
            copia = sqlite3.connect(destino)
            try:
                origen.backup(copia)
            finally:
                copia.close()
        except sqlite3.Error as exc:
            logger.exception("Falló el respaldo de la base de datos.")
            raise DatabaseError(f"No se pudo crear el respaldo: {exc}") from exc
        finally:
            origen.close()
        return destino

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

    def _version_actual(self) -> int:
        conn = self._connect()
        try:
            return int(conn.execute("PRAGMA user_version;").fetchone()[0])
        finally:
            conn.close()

    def _ejecutar_script(self, script: str, version_resultante: int) -> None:
        """Ejecuta un script SQL y fija la versión, TODO en una sola transacción."""
        conn = self._connect()
        try:
            conn.executescript(
                "BEGIN IMMEDIATE;\n"
                f"{script}\n"
                f"PRAGMA user_version = {version_resultante};\n"
                "COMMIT;"
            )
        except sqlite3.Error as exc:
            self._rollback_quietly(conn)
            logger.exception("Falló el script hacia la versión %s.", version_resultante)
            raise SchemaInitializationError(
                f"No se pudo llevar la base a la versión {version_resultante}: {exc}. "
                "La base de datos quedó sin cambios."
            ) from exc
        finally:
            conn.close()

    @staticmethod
    def _leer(ruta: Path) -> str:
        try:
            return ruta.read_text(encoding="utf-8")
        except OSError as exc:
            logger.exception("No se pudo leer el script %s", ruta)
            raise SchemaInitializationError(f"No se pudo leer {ruta}") from exc

    @staticmethod
    def _listar_migraciones(carpeta: Path) -> dict[int, Path]:
        """{versión: archivo} para los archivos con forma NNN_descripcion.sql."""
        if not carpeta.is_dir():
            return {}
        migraciones: dict[int, Path] = {}
        for archivo in carpeta.glob("*.sql"):
            coincidencia = re.match(r"^(\d{3})_.+\.sql$", archivo.name)
            if coincidencia:
                migraciones[int(coincidencia.group(1))] = archivo
        return migraciones

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
