"""
Repositorio SQLite de facturas de proveedor.

Ruta: src/infrastructure/repositories/sqlite_factura_repository.py
"""

import sqlite3
from typing import Any, Final

from src.business.models.gasto import DatosFactura, FacturaProveedor
from src.infrastructure.repositories.conversiones import (
    escapar_like,
    fecha_a_texto,
    texto_a_fecha_obligatoria,
)

# Cada factura con el nombre del proveedor y su valor ya asignado a plantas
# (suma de los gastos NO anulados). El saldo se deriva de estos dos valores.
_SQL_FACTURAS: Final[str] = """
    SELECT f.*, p.nombre AS proveedor_nombre,
           COALESCE((SELECT SUM(g.valor_total) FROM gastos g
                     WHERE g.factura_id = f.id AND g.anulado = 0), 0) AS valor_asignado
    FROM facturas_proveedor f
    JOIN proveedores p ON p.id = f.proveedor_id
"""


class SqliteFacturaRepository:
    """Acceso a la tabla facturas_proveedor."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def insertar(self, datos: DatosFactura) -> int:
        cursor = self._conn.execute(
            "INSERT INTO facturas_proveedor "
            "(proveedor_id, numero_factura, fecha_factura, valor_total, observaciones) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                datos.proveedor_id,
                datos.numero_factura,
                fecha_a_texto(datos.fecha_factura),
                datos.valor_total,
                datos.observaciones,
            ),
        )
        return int(cursor.lastrowid)  # type: ignore[arg-type]

    def obtener(self, factura_id: int) -> FacturaProveedor | None:
        fila = self._conn.execute(_SQL_FACTURAS + " WHERE f.id = ?", (factura_id,)).fetchone()
        return _fila_a_factura(fila) if fila is not None else None

    def existe_numero(self, proveedor_id: int, numero: str) -> bool:
        fila = self._conn.execute(
            "SELECT 1 FROM facturas_proveedor "
            "WHERE proveedor_id = ? AND trim(numero_factura) = trim(?) COLLATE NOCASE LIMIT 1",
            (proveedor_id, numero),
        ).fetchone()
        return fila is not None

    def listar_con_saldo(self, texto: str | None = None) -> list[FacturaProveedor]:
        sql = f"SELECT * FROM ({_SQL_FACTURAS}) WHERE valor_total - valor_asignado > 0"
        parametros: list[Any] = []
        if texto:
            patron = f"%{escapar_like(texto)}%"
            sql += " AND (numero_factura LIKE ? ESCAPE '\\' OR proveedor_nombre LIKE ? ESCAPE '\\')"
            parametros = [patron, patron]
        sql += " ORDER BY fecha_factura DESC, id DESC LIMIT 100"
        return [_fila_a_factura(f) for f in self._conn.execute(sql, parametros).fetchall()]


def _fila_a_factura(fila: sqlite3.Row) -> FacturaProveedor:
    return FacturaProveedor(
        id=fila["id"],
        datos=DatosFactura(
            proveedor_id=fila["proveedor_id"],
            numero_factura=fila["numero_factura"],
            fecha_factura=texto_a_fecha_obligatoria(fila["fecha_factura"]),
            valor_total=fila["valor_total"],
            observaciones=fila["observaciones"],
        ),
        proveedor_nombre=fila["proveedor_nombre"],
        valor_asignado=int(fila["valor_asignado"]),
    )
