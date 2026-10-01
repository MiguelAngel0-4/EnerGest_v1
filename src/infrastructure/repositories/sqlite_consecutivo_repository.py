"""
Repositorio SQLite de consecutivos.

Ruta: src/infrastructure/repositories/sqlite_consecutivo_repository.py

Cumple el contrato IConsecutivoRepository. La fuente de verdad de los
números EN USO es la tabla plantas; historial_consecutivos guarda la
memoria de quién tuvo cada número y durante qué periodo.
"""

import sqlite3
from datetime import date
from typing import Final

from src.business.exceptions import PersistenciaError
from src.business.models.planta import RegistroConsecutivo
from src.infrastructure.repositories.conversiones import (
    fecha_a_texto,
    texto_a_fecha,
    texto_a_fecha_obligatoria,
)

_COLUMNAS: Final[str] = (
    "planta_id, numero, fecha_asignacion, fecha_liberacion, motivo_liberacion"
)


class SqliteConsecutivoRepository:
    """Acceso a los números en uso y a la tabla historial_consecutivos."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def numeros_en_uso(self) -> set[int]:
        filas = self._conn.execute(
            "SELECT numero_consecutivo FROM plantas WHERE numero_consecutivo IS NOT NULL"
        ).fetchall()
        return {int(f[0]) for f in filas}

    def abrir_registro(self, planta_id: int, numero: int, fecha: date) -> None:
        self._conn.execute(
            "INSERT INTO historial_consecutivos (planta_id, numero, fecha_asignacion) "
            "VALUES (?, ?, ?)",
            (planta_id, numero, fecha_a_texto(fecha)),
        )

    def cerrar_registro(self, planta_id: int, fecha: date, motivo: str) -> None:
        cursor = self._conn.execute(
            "UPDATE historial_consecutivos "
            "SET fecha_liberacion = ?, motivo_liberacion = ? "
            "WHERE planta_id = ? AND fecha_liberacion IS NULL",
            (fecha_a_texto(fecha), motivo, planta_id),
        )
        if cursor.rowcount == 0:
            # Si no había registro abierto, el historial está inconsistente:
            # se lanza el error para que la Unidad de Trabajo deshaga todo.
            raise PersistenciaError(
                f"No se encontró un consecutivo vigente para la planta id={planta_id}."
            )

    def ultimo_numero_de(self, planta_id: int) -> int | None:
        fila = self._conn.execute(
            "SELECT numero FROM historial_consecutivos WHERE planta_id = ? "
            "ORDER BY fecha_asignacion DESC, id DESC LIMIT 1",
            (planta_id,),
        ).fetchone()
        return int(fila[0]) if fila is not None else None

    def historial_de_planta(self, planta_id: int) -> list[RegistroConsecutivo]:
        filas = self._conn.execute(
            f"SELECT {_COLUMNAS} FROM historial_consecutivos WHERE planta_id = ? "
            "ORDER BY fecha_asignacion, id",
            (planta_id,),
        ).fetchall()
        return [_fila_a_registro(f) for f in filas]

    def historial_de_numero(self, numero: int) -> list[RegistroConsecutivo]:
        filas = self._conn.execute(
            f"SELECT {_COLUMNAS} FROM historial_consecutivos WHERE numero = ? "
            "ORDER BY fecha_asignacion, id",
            (numero,),
        ).fetchall()
        return [_fila_a_registro(f) for f in filas]


def _fila_a_registro(fila: sqlite3.Row) -> RegistroConsecutivo:
    """Convierte una fila del historial en un RegistroConsecutivo."""
    return RegistroConsecutivo(
        planta_id=fila["planta_id"],
        numero=fila["numero"],
        fecha_asignacion=texto_a_fecha_obligatoria(fila["fecha_asignacion"]),
        fecha_liberacion=texto_a_fecha(fila["fecha_liberacion"]),
        motivo_liberacion=fila["motivo_liberacion"],
    )
