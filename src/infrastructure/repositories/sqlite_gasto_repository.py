"""
Repositorio SQLite de gastos.

Ruta: src/infrastructure/repositories/sqlite_gasto_repository.py
"""

import sqlite3
from typing import Final

from src.business.models.gasto import DatosGasto, Gasto, GastoDetalle, ResumenGastos
from src.infrastructure.repositories.conversiones import (
    fecha_a_texto,
    texto_a_fecha_hora,
    texto_a_fecha_obligatoria,
)

# Gasto + nombres de categoría, factura y proveedor en UNA consulta (evita
# consultar uno por uno, el clásico problema "N+1").
_SQL_DETALLE: Final[str] = """
    SELECT g.*, c.nombre AS categoria, f.numero_factura, p.nombre AS proveedor
    FROM gastos g
    JOIN categorias_gasto c ON c.id = g.categoria_id
    LEFT JOIN facturas_proveedor f ON f.id = g.factura_id
    LEFT JOIN proveedores p ON p.id = f.proveedor_id
"""


class SqliteGastoRepository:
    """Acceso a la tabla gastos."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def insertar(
        self, planta_id: int, datos: DatosGasto, mantenimiento_id: int | None = None
    ) -> int:
        cursor = self._conn.execute(
            "INSERT INTO gastos (planta_id, categoria_id, factura_id, mantenimiento_id, fecha, "
            "descripcion, cantidad, unidad, valor_total) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                planta_id,
                datos.categoria_id,
                datos.factura_id,
                mantenimiento_id,
                fecha_a_texto(datos.fecha),
                datos.descripcion,
                datos.cantidad,
                datos.unidad,
                datos.valor_total,
            ),
        )
        return int(cursor.lastrowid)  # type: ignore[arg-type]

    def obtener(self, gasto_id: int) -> Gasto | None:
        fila = self._conn.execute("SELECT * FROM gastos WHERE id = ?", (gasto_id,)).fetchone()
        return _fila_a_gasto(fila) if fila is not None else None

    def anular(self, gasto_id: int, motivo: str) -> None:
        self._conn.execute(
            "UPDATE gastos SET anulado = 1, motivo_anulacion = ? WHERE id = ?",
            (motivo, gasto_id),
        )

    def listar_por_planta(
        self, planta_id: int, incluir_anulados: bool = False
    ) -> list[GastoDetalle]:
        sql = _SQL_DETALLE + " WHERE g.planta_id = ?"
        if not incluir_anulados:
            sql += " AND g.anulado = 0"
        sql += " ORDER BY g.fecha DESC, g.id DESC"
        return [
            GastoDetalle(
                gasto=_fila_a_gasto(fila),
                categoria=fila["categoria"],
                numero_factura=fila["numero_factura"],
                proveedor=fila["proveedor"],
            )
            for fila in self._conn.execute(sql, (planta_id,)).fetchall()
        ]

    def resumen_por_planta(self, planta_id: int) -> ResumenGastos:
        totales = self._conn.execute(
            "SELECT COALESCE(SUM(valor_total), 0) AS total, COUNT(*) AS cantidad, "
            "COALESCE(SUM(CASE WHEN factura_id IS NULL THEN valor_total END), 0) AS sin_soporte "
            "FROM gastos WHERE planta_id = ? AND anulado = 0",
            (planta_id,),
        ).fetchone()
        por_categoria = self._conn.execute(
            "SELECT c.nombre, SUM(g.valor_total) AS total FROM gastos g "
            "JOIN categorias_gasto c ON c.id = g.categoria_id "
            "WHERE g.planta_id = ? AND g.anulado = 0 "
            "GROUP BY c.id ORDER BY total DESC, c.nombre",
            (planta_id,),
        ).fetchall()
        return ResumenGastos(
            total=int(totales["total"]),
            cantidad=int(totales["cantidad"]),
            sin_soporte=int(totales["sin_soporte"]),
            por_categoria=tuple((f["nombre"], int(f["total"])) for f in por_categoria),
        )


def _fila_a_gasto(fila: sqlite3.Row) -> Gasto:
    return Gasto(
        id=fila["id"],
        planta_id=fila["planta_id"],
        datos=DatosGasto(
            categoria_id=fila["categoria_id"],
            fecha=texto_a_fecha_obligatoria(fila["fecha"]),
            descripcion=fila["descripcion"],
            valor_total=fila["valor_total"],
            cantidad=fila["cantidad"],
            unidad=fila["unidad"],
            factura_id=fila["factura_id"],
        ),
        mantenimiento_id=fila["mantenimiento_id"],
        anulado=bool(fila["anulado"]),
        motivo_anulacion=fila["motivo_anulacion"],
        fecha_registro=texto_a_fecha_hora(fila["fecha_registro"]),
    )
