"""
Repositorio SQLite de consultas de reportes (solo lectura).

Ruta: src/infrastructure/repositories/sqlite_reporte_repository.py

Todas las sumas se hacen en SQLite con GROUP BY: la base de datos devuelve
pocas filas ya resumidas, en lugar de miles de movimientos para sumar en Python.
Solo cuentan los movimientos VIGENTES (anulado = 0).
"""

import sqlite3
from datetime import date
from typing import Any, Final

from src.business.models.rentabilidad import MesFinanciero, Movimiento, TotalesPlanta
from src.infrastructure.repositories.conversiones import fecha_a_texto, texto_a_fecha_obligatoria
from src.shared.formatters import formatear_consecutivo

# Filtro de período reutilizable: un extremo en NULL significa "sin límite".
_EN_PERIODO: Final[str] = "(:desde IS NULL OR {c} >= :desde) AND (:hasta IS NULL OR {c} <= :hasta)"


def _periodo(desde: date | None, hasta: date | None) -> dict[str, Any]:
    return {"desde": fecha_a_texto(desde), "hasta": fecha_a_texto(hasta)}


class SqliteReporteRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def totales_por_planta(
        self, desde: date | None = None, hasta: date | None = None
    ) -> dict[int, TotalesPlanta]:
        parametros = _periodo(desde, hasta)
        ingresos = self._conn.execute(
            "SELECT planta_id, "
            "SUM(CASE WHEN tipo = 'ALQUILER' THEN valor ELSE 0 END) AS alquiler, "
            "SUM(CASE WHEN tipo = 'VENTA' THEN valor ELSE 0 END) AS venta, "
            "SUM(CASE WHEN tipo = 'OTRO' THEN valor ELSE 0 END) AS otros "
            f"FROM ingresos WHERE anulado = 0 AND {_EN_PERIODO.format(c='fecha')} "
            "GROUP BY planta_id",
            parametros,
        ).fetchall()
        gastos = self._conn.execute(
            "SELECT planta_id, SUM(valor_total) AS total FROM gastos "
            f"WHERE anulado = 0 AND {_EN_PERIODO.format(c='fecha')} GROUP BY planta_id",
            parametros,
        ).fetchall()
        totales: dict[int, TotalesPlanta] = {}
        for f in ingresos:
            totales[f["planta_id"]] = TotalesPlanta(f["alquiler"], f["venta"], f["otros"], 0)
        for f in gastos:
            base = totales.get(f["planta_id"], TotalesPlanta())
            totales[f["planta_id"]] = TotalesPlanta(
                base.ingresos_alquiler, base.ingresos_venta, base.ingresos_otros, f["total"]
            )
        return totales

    def gastos_por_categoria(
        self, planta_id: int, desde: date | None = None, hasta: date | None = None
    ) -> list[tuple[str, int]]:
        filas = self._conn.execute(
            "SELECT c.nombre, SUM(g.valor_total) AS total FROM gastos g "
            "JOIN categorias_gasto c ON c.id = g.categoria_id "
            f"WHERE g.planta_id = :planta AND g.anulado = 0 AND {_EN_PERIODO.format(c='g.fecha')} "
            "GROUP BY c.id ORDER BY total DESC, c.nombre",
            {"planta": planta_id, **_periodo(desde, hasta)},
        ).fetchall()
        return [(f["nombre"], f["total"]) for f in filas]

    def meses(self, desde: date | None = None, hasta: date | None = None) -> list[MesFinanciero]:
        filas = self._conn.execute(
            "SELECT mes, SUM(ingresos) AS ingresos, SUM(gastos) AS gastos FROM ("
            "  SELECT strftime('%Y-%m', fecha) AS mes, valor AS ingresos, 0 AS gastos"
            f"  FROM ingresos WHERE anulado = 0 AND {_EN_PERIODO.format(c='fecha')}"
            "  UNION ALL"
            "  SELECT strftime('%Y-%m', fecha), 0, valor_total"
            f"  FROM gastos WHERE anulado = 0 AND {_EN_PERIODO.format(c='fecha')}"
            ") GROUP BY mes ORDER BY mes",
            _periodo(desde, hasta),
        ).fetchall()
        return [MesFinanciero(f["mes"], f["ingresos"], f["gastos"]) for f in filas]

    def horas_uso_alquiler(
        self, planta_id: int, desde: date | None = None, hasta: date | None = None
    ) -> int:
        fila = self._conn.execute(
            "SELECT COALESCE(SUM(horas), 0) FROM ("
            "  SELECT (SELECT MAX(h.horometro) - MIN(h.horometro) FROM historial_estados h"
            "          WHERE h.alquiler_id = a.id AND h.horometro IS NOT NULL"
            "          HAVING COUNT(h.horometro) >= 2) AS horas"
            "  FROM alquileres a"
            f"  WHERE a.planta_id = :planta AND {_EN_PERIODO.format(c='a.fecha_inicio')})",
            {"planta": planta_id, **_periodo(desde, hasta)},
        ).fetchone()
        return int(fila[0])

    def saldo_por_cobrar(self, planta_id: int | None = None) -> int:
        fila = self._conn.execute(
            "SELECT COALESCE(SUM(saldo), 0) FROM ("
            "  SELECT a.valor_liquidado - COALESCE((SELECT SUM(i.valor) FROM ingresos i"
            "         WHERE i.alquiler_id = a.id AND i.anulado = 0), 0) AS saldo"
            "  FROM alquileres a"
            "  WHERE a.fecha_fin IS NOT NULL AND (:planta IS NULL OR a.planta_id = :planta)"
            ") WHERE saldo > 0",
            {"planta": planta_id},
        ).fetchone()
        return int(fila[0])

    def movimientos(self, desde: date | None = None, hasta: date | None = None) -> list[Movimiento]:
        filas = self._conn.execute(
            "SELECT i.fecha, p.numero_consecutivo, p.marca, p.modelo, 'Ingreso' AS tipo,"
            "  CASE i.tipo WHEN 'ALQUILER' THEN 'Alquiler' WHEN 'VENTA' THEN 'Venta'"
            "  ELSE 'Otro' END AS concepto,"
            "  i.descripcion, i.numero_documento AS documento, i.valor"
            " FROM ingresos i JOIN plantas p ON p.id = i.planta_id"
            f" WHERE i.anulado = 0 AND {_EN_PERIODO.format(c='i.fecha')}"
            " UNION ALL"
            " SELECT g.fecha, p.numero_consecutivo, p.marca, p.modelo, 'Gasto', c.nombre,"
            "  g.descripcion,"
            "  f.numero_factura, g.valor_total"
            " FROM gastos g JOIN plantas p ON p.id = g.planta_id"
            " JOIN categorias_gasto c ON c.id = g.categoria_id"
            " LEFT JOIN facturas_proveedor f ON f.id = g.factura_id"
            f" WHERE g.anulado = 0 AND {_EN_PERIODO.format(c='g.fecha')}"
            " ORDER BY 1, 5 DESC, 2",
            _periodo(desde, hasta),
        ).fetchall()
        return [
            Movimiento(
                texto_a_fecha_obligatoria(f["fecha"]),
                # El formato del número sale de settings (vía formatear_consecutivo),
                # nunca escrito a mano en el SQL: así hay una sola fuente de verdad.
                " · ".join(
                    [
                        formatear_consecutivo(f["numero_consecutivo"])
                        if f["numero_consecutivo"] is not None
                        else "Sin número",
                        " ".join(filter(None, [f["marca"], f["modelo"]])),
                    ]
                ),
                f["tipo"],
                f["concepto"],
                f["descripcion"],
                f["documento"],
                f["valor"],
            )
            for f in filas
        ]
