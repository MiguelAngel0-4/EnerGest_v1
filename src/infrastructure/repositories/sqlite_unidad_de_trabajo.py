"""
Unidad de Trabajo implementada sobre SQLite.

Ruta: src/infrastructure/repositories/sqlite_unidad_de_trabajo.py

Es el "carrito de compras" real:
- Al entrar (__enter__) abre una transacción BEGIN IMMEDIATE a través del
  DatabaseManager y entrega a los repositorios la MISMA conexión.
- Al salir (__exit__) confirma si todo salió bien o deshace si hubo error.

También es el ÚNICO punto donde los errores técnicos de la base de datos
se traducen a PersistenciaError, para que el negocio nunca dependa de SQLite.
"""

import sqlite3
from contextlib import AbstractContextManager
from types import TracebackType
from typing import Self

from src.business.exceptions import PersistenciaError
from src.business.interfaces.unidad_de_trabajo import FabricaUnidadDeTrabajo
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.exceptions import (
    DatabaseError,
    DatabaseIntegrityError,
    DatabaseLockedError,
)
from src.infrastructure.repositories.sqlite_consecutivo_repository import (
    SqliteConsecutivoRepository,
)
from src.infrastructure.repositories.sqlite_factura_repository import SqliteFacturaRepository
from src.infrastructure.repositories.sqlite_gasto_repository import SqliteGastoRepository
from src.infrastructure.repositories.sqlite_historial_estado_repository import (
    SqliteHistorialEstadoRepository,
)
from src.infrastructure.repositories.sqlite_mantenimiento_repository import (
    SqliteMantenimientoRepository,
)
from src.infrastructure.repositories.sqlite_planta_repository import SqlitePlantaRepository
from src.infrastructure.repositories.sqlite_proveedor_repository import (
    SqliteCategoriaRepository,
    SqliteProveedorRepository,
)


class SqliteUnidadDeTrabajo:
    """Agrupa los repositorios SQLite dentro de una sola transacción."""

    plantas: SqlitePlantaRepository
    consecutivos: SqliteConsecutivoRepository
    historial_estados: SqliteHistorialEstadoRepository
    gastos: SqliteGastoRepository
    facturas: SqliteFacturaRepository
    proveedores: SqliteProveedorRepository
    categorias: SqliteCategoriaRepository
    mantenimientos: SqliteMantenimientoRepository

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db
        self._transaccion: AbstractContextManager[sqlite3.Connection] | None = None

    def __enter__(self) -> Self:
        self._transaccion = self._db.transaction()
        try:
            conn = self._transaccion.__enter__()
        except DatabaseError as exc:
            self._transaccion = None
            raise _traducir(exc) from exc

        # Todos los repositorios comparten la misma conexión = misma transacción.
        self.plantas = SqlitePlantaRepository(conn)
        self.consecutivos = SqliteConsecutivoRepository(conn)
        self.historial_estados = SqliteHistorialEstadoRepository(conn)
        self.gastos = SqliteGastoRepository(conn)
        self.facturas = SqliteFacturaRepository(conn)
        self.proveedores = SqliteProveedorRepository(conn)
        self.categorias = SqliteCategoriaRepository(conn)
        self.mantenimientos = SqliteMantenimientoRepository(conn)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._transaccion is None:
            return
        transaccion, self._transaccion = self._transaccion, None
        try:
            # Sin error: COMMIT. Con error: ROLLBACK y el error sigue su camino.
            transaccion.__exit__(exc_type, exc, tb)
        except DatabaseError as db_exc:
            # Errores de SQLite (en el COMMIT o dentro del bloque) llegan aquí
            # ya traducidos por el DatabaseManager; los convertimos al negocio.
            raise _traducir(db_exc) from db_exc


def _traducir(exc: DatabaseError) -> PersistenciaError:
    """Convierte un error de la capa de datos en un mensaje apto para el usuario."""
    if isinstance(exc, DatabaseLockedError):
        return PersistenciaError(str(exc))
    if isinstance(exc, DatabaseIntegrityError):
        return PersistenciaError(
            "La operación no cumple una regla de integridad de la base de datos. "
            "No se guardó ningún cambio."
        )
    return PersistenciaError(
        "Ocurrió un error al acceder a la base de datos. No se guardó ningún cambio. "
        "Los detalles quedaron registrados en el archivo de log."
    )


def crear_fabrica_uow(db: DatabaseManager) -> FabricaUnidadDeTrabajo:
    """
    Devuelve la fábrica que el PlantaService usará para crear unidades de trabajo.

    Se usará en main.py, que es donde se "ensamblan" las capas:
        servicio = PlantaService(crear_fabrica_uow(db), ConsecutivoService())
    """
    return lambda: SqliteUnidadDeTrabajo(db)
