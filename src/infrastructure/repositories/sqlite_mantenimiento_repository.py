"""
Repositorio SQLite de mantenimientos.

Ruta: src/infrastructure/repositories/sqlite_mantenimiento_repository.py
"""

import sqlite3
from typing import Final

from src.business.models.mantenimiento import (
    DatosMantenimiento,
    Mantenimiento,
    TipoMantenimiento,
)
from src.infrastructure.repositories.conversiones import (
    fecha_a_texto,
    texto_a_fecha,
    texto_a_fecha_obligatoria,
)

# Cada mantenimiento con su costo: la suma de sus gastos NO anulados (calculada).
_SQL_BASE: Final[str] = """
    SELECT m.*,
           COALESCE((SELECT SUM(g.valor_total) FROM gastos g
                     WHERE g.mantenimiento_id = m.id AND g.anulado = 0), 0) AS costo_total
    FROM mantenimientos m
"""
_ORDEN: Final[str] = " ORDER BY m.fecha DESC, m.id DESC"


class SqliteMantenimientoRepository:
    """Acceso a la tabla mantenimientos."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def insertar(self, planta_id: int, datos: DatosMantenimiento) -> int:
        cursor = self._conn.execute(
            "INSERT INTO mantenimientos (planta_id, fecha, tipo, horometro, tecnico, "
            "descripcion, proxima_fecha, proximo_horometro) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                planta_id,
                fecha_a_texto(datos.fecha),
                datos.tipo.value,
                datos.horometro,
                datos.tecnico,
                datos.descripcion,
                fecha_a_texto(datos.proxima_fecha),
                datos.proximo_horometro,
            ),
        )
        return int(cursor.lastrowid)  # type: ignore[arg-type]

    def obtener(self, mantenimiento_id: int) -> Mantenimiento | None:
        fila = self._conn.execute(_SQL_BASE + " WHERE m.id = ?", (mantenimiento_id,)).fetchone()
        return _fila_a_mantenimiento(fila) if fila is not None else None

    def anular(self, mantenimiento_id: int, motivo: str) -> None:
        self._conn.execute(
            "UPDATE mantenimientos SET anulado = 1, motivo_anulacion = ? WHERE id = ?",
            (motivo, mantenimiento_id),
        )

    def listar_por_planta(
        self, planta_id: int, incluir_anulados: bool = False
    ) -> list[Mantenimiento]:
        sql = _SQL_BASE + " WHERE m.planta_id = ?"
        if not incluir_anulados:
            sql += " AND m.anulado = 0"
        filas = self._conn.execute(sql + _ORDEN, (planta_id,)).fetchall()
        return [_fila_a_mantenimiento(f) for f in filas]

    def ultimo_vigente(self, planta_id: int) -> Mantenimiento | None:
        fila = self._conn.execute(
            _SQL_BASE + " WHERE m.planta_id = ? AND m.anulado = 0" + _ORDEN + " LIMIT 1",
            (planta_id,),
        ).fetchone()
        return _fila_a_mantenimiento(fila) if fila is not None else None

    def ultimos_por_planta(self) -> dict[int, Mantenimiento]:
        # Para cada planta, el id de su último mantenimiento vigente.
        filas = self._conn.execute(
            _SQL_BASE
            + """ WHERE m.id = (SELECT m2.id FROM mantenimientos m2
                               WHERE m2.planta_id = m.planta_id AND m2.anulado = 0
                               ORDER BY m2.fecha DESC, m2.id DESC LIMIT 1)"""
        ).fetchall()
        return {f["planta_id"]: _fila_a_mantenimiento(f) for f in filas}

    def tecnicos_registrados(self) -> list[str]:
        filas = self._conn.execute(
            "SELECT trim(tecnico) AS tecnico FROM mantenimientos "
            "WHERE tecnico IS NOT NULL AND trim(tecnico) <> '' "
            "GROUP BY trim(tecnico) COLLATE NOCASE ORDER BY trim(tecnico) COLLATE NOCASE"
        ).fetchall()
        return [f["tecnico"] for f in filas]


def _fila_a_mantenimiento(fila: sqlite3.Row) -> Mantenimiento:
    return Mantenimiento(
        id=fila["id"],
        planta_id=fila["planta_id"],
        datos=DatosMantenimiento(
            fecha=texto_a_fecha_obligatoria(fila["fecha"]),
            tipo=TipoMantenimiento(fila["tipo"]),
            horometro=fila["horometro"] if fila["horometro"] is not None else 0,
            descripcion=fila["descripcion"],
            tecnico=fila["tecnico"],
            proxima_fecha=texto_a_fecha(fila["proxima_fecha"]),
            proximo_horometro=fila["proximo_horometro"],
        ),
        anulado=bool(fila["anulado"]),
        motivo_anulacion=fila["motivo_anulacion"],
        costo_total=int(fila["costo_total"]),
    )
