"""
Repositorio SQLite del historial de estados.

Ruta: src/infrastructure/repositories/sqlite_historial_estado_repository.py

Cumple el contrato IHistorialEstadoRepository.
"""

import sqlite3

from src.business.models.estado_planta import EstadoPlanta
from src.business.models.planta import CambioEstado
from src.infrastructure.repositories.conversiones import fecha_a_texto, texto_a_fecha_obligatoria


class SqliteHistorialEstadoRepository:
    """Acceso a la tabla historial_estados."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def registrar(self, cambio: CambioEstado) -> None:
        self._conn.execute(
            "INSERT INTO historial_estados "
            "(planta_id, estado_anterior, estado_nuevo, fecha, motivo) VALUES (?, ?, ?, ?, ?)",
            (
                cambio.planta_id,
                cambio.estado_anterior.value if cambio.estado_anterior else None,
                cambio.estado_nuevo.value,
                fecha_a_texto(cambio.fecha),
                cambio.motivo,
            ),
        )

    def listar_por_planta(self, planta_id: int) -> list[CambioEstado]:
        # Orden por fecha y, en el mismo día, por orden de registro (id).
        filas = self._conn.execute(
            "SELECT planta_id, estado_anterior, estado_nuevo, fecha, motivo "
            "FROM historial_estados WHERE planta_id = ? ORDER BY fecha, id",
            (planta_id,),
        ).fetchall()
        return [
            CambioEstado(
                planta_id=f["planta_id"],
                estado_anterior=EstadoPlanta(f["estado_anterior"]) if f["estado_anterior"] else None,
                estado_nuevo=EstadoPlanta(f["estado_nuevo"]),
                fecha=texto_a_fecha_obligatoria(f["fecha"]),
                motivo=f["motivo"],
            )
            for f in filas
        ]
