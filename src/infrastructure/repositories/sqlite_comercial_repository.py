"""
Repositorios SQLite del módulo comercial: clientes, alquileres e ingresos.

Ruta: src/infrastructure/repositories/sqlite_comercial_repository.py
"""

import sqlite3
from datetime import date
from typing import Final

from src.business.models.comercial import (
    Alquiler,
    Cliente,
    DatosContrato,
    DatosIngreso,
    Ingreso,
    ModalidadAlquiler,
    TipoIngreso,
)
from src.infrastructure.repositories.conversiones import (
    fecha_a_texto,
    texto_a_fecha,
    texto_a_fecha_obligatoria,
)

# Contrato con el nombre del cliente y dos valores CALCULADOS:
# - cobrado: suma de sus ingresos vigentes;
# - horas_uso: diferencia entre la lectura de regreso y la de salida, tomadas del
#   historial de estados ligado al contrato (NULL si aún falta alguna lectura).
_SQL_ALQUILER: Final[str] = """
    SELECT a.*, c.nombre AS cliente_nombre,
           COALESCE((SELECT SUM(i.valor) FROM ingresos i
                     WHERE i.alquiler_id = a.id AND i.anulado = 0), 0) AS cobrado,
           (SELECT MAX(h.horometro) - MIN(h.horometro) FROM historial_estados h
            WHERE h.alquiler_id = a.id AND h.horometro IS NOT NULL
            HAVING COUNT(h.horometro) >= 2) AS horas_uso
    FROM alquileres a
    JOIN clientes c ON c.id = a.cliente_id
"""

_SQL_INGRESO: Final[str] = """
    SELECT i.*, c.nombre AS cliente_nombre
    FROM ingresos i
    LEFT JOIN clientes c ON c.id = i.cliente_id
"""


class SqliteClienteRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def insertar(self, nombre: str, documento: str | None, telefono: str | None) -> int:
        cursor = self._conn.execute(
            "INSERT INTO clientes (nombre, documento, telefono) VALUES (?, ?, ?)",
            (nombre, documento, telefono),
        )
        return int(cursor.lastrowid)  # type: ignore[arg-type]

    def obtener(self, cliente_id: int) -> Cliente | None:
        fila = self._conn.execute("SELECT * FROM clientes WHERE id = ?", (cliente_id,)).fetchone()
        return _fila_a_cliente(fila) if fila else None

    def listar(self) -> list[Cliente]:
        filas = self._conn.execute(
            "SELECT * FROM clientes WHERE activo = 1 ORDER BY nombre COLLATE NOCASE"
        ).fetchall()
        return [_fila_a_cliente(f) for f in filas]

    def existe_nombre(self, nombre: str) -> bool:
        return self._existe("trim(nombre) = trim(?) COLLATE NOCASE", nombre)

    def existe_documento(self, documento: str) -> bool:
        return self._existe("trim(documento) = trim(?) COLLATE NOCASE", documento)

    def _existe(self, condicion: str, valor: str) -> bool:
        sql = f"SELECT 1 FROM clientes WHERE {condicion} LIMIT 1"
        return self._conn.execute(sql, (valor,)).fetchone() is not None


class SqliteAlquilerRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def insertar(self, planta_id: int, contrato: DatosContrato, fecha_inicio: date) -> int:
        cursor = self._conn.execute(
            "INSERT INTO alquileres (planta_id, cliente_id, fecha_inicio, modalidad, tarifa, "
            "observaciones) VALUES (?, ?, ?, ?, ?, ?)",
            (
                planta_id,
                contrato.cliente_id,
                fecha_a_texto(fecha_inicio),
                contrato.modalidad.value,
                contrato.tarifa,
                contrato.observaciones,
            ),
        )
        return int(cursor.lastrowid)  # type: ignore[arg-type]

    def obtener(self, alquiler_id: int) -> Alquiler | None:
        fila = self._conn.execute(_SQL_ALQUILER + " WHERE a.id = ?", (alquiler_id,)).fetchone()
        return _fila_a_alquiler(fila) if fila else None

    def activo_de(self, planta_id: int) -> Alquiler | None:
        fila = self._conn.execute(
            _SQL_ALQUILER + " WHERE a.planta_id = ? AND a.fecha_fin IS NULL", (planta_id,)
        ).fetchone()
        return _fila_a_alquiler(fila) if fila else None

    def cerrar(self, alquiler_id: int, fecha_fin: date, valor_liquidado: int) -> None:
        # Fecha y valor en UNA sentencia: el CHECK exige cerrado <=> liquidado.
        self._conn.execute(
            "UPDATE alquileres SET fecha_fin = ?, valor_liquidado = ? WHERE id = ?",
            (fecha_a_texto(fecha_fin), valor_liquidado, alquiler_id),
        )

    def actualizar_condiciones(self, alquiler_id: int, contrato: DatosContrato) -> None:
        self._conn.execute(
            "UPDATE alquileres SET cliente_id = ?, modalidad = ?, tarifa = ?, observaciones = ? "
            "WHERE id = ?",
            (
                contrato.cliente_id,
                contrato.modalidad.value,
                contrato.tarifa,
                contrato.observaciones,
                alquiler_id,
            ),
        )

    def listar_por_planta(self, planta_id: int) -> list[Alquiler]:
        filas = self._conn.execute(
            _SQL_ALQUILER + " WHERE a.planta_id = ? ORDER BY a.fecha_inicio DESC, a.id DESC",
            (planta_id,),
        ).fetchall()
        return [_fila_a_alquiler(f) for f in filas]

    def clientes_actuales(self) -> dict[int, str]:
        filas = self._conn.execute(
            "SELECT a.planta_id, c.nombre FROM alquileres a JOIN clientes c ON c.id = a.cliente_id "
            "WHERE a.fecha_fin IS NULL"
        ).fetchall()
        return {f["planta_id"]: f["nombre"] for f in filas}


class SqliteIngresoRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def insertar(
        self,
        planta_id: int,
        tipo: TipoIngreso,
        datos: DatosIngreso,
        alquiler_id: int | None = None,
        cliente_id: int | None = None,
    ) -> int:
        cursor = self._conn.execute(
            "INSERT INTO ingresos (planta_id, tipo, alquiler_id, cliente_id, fecha, descripcion, "
            "numero_documento, valor) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                planta_id,
                tipo.value,
                alquiler_id,
                cliente_id,
                fecha_a_texto(datos.fecha),
                datos.descripcion,
                datos.numero_documento,
                datos.valor,
            ),
        )
        return int(cursor.lastrowid)  # type: ignore[arg-type]

    def obtener(self, ingreso_id: int) -> Ingreso | None:
        fila = self._conn.execute(_SQL_INGRESO + " WHERE i.id = ?", (ingreso_id,)).fetchone()
        return _fila_a_ingreso(fila) if fila else None

    def anular(self, ingreso_id: int, motivo: str) -> None:
        self._conn.execute(
            "UPDATE ingresos SET anulado = 1, motivo_anulacion = ? WHERE id = ?",
            (motivo, ingreso_id),
        )

    def listar_por_planta(self, planta_id: int, incluir_anulados: bool = False) -> list[Ingreso]:
        sql = _SQL_INGRESO + " WHERE i.planta_id = ?"
        if not incluir_anulados:
            sql += " AND i.anulado = 0"
        filas = self._conn.execute(sql + " ORDER BY i.fecha DESC, i.id DESC", (planta_id,))
        return [_fila_a_ingreso(f) for f in filas.fetchall()]


def _fila_a_cliente(fila: sqlite3.Row) -> Cliente:
    return Cliente(
        fila["id"], fila["nombre"], fila["documento"], fila["telefono"], bool(fila["activo"])
    )


def _fila_a_alquiler(fila: sqlite3.Row) -> Alquiler:
    return Alquiler(
        id=fila["id"],
        planta_id=fila["planta_id"],
        cliente_id=fila["cliente_id"],
        cliente_nombre=fila["cliente_nombre"],
        fecha_inicio=texto_a_fecha_obligatoria(fila["fecha_inicio"]),
        fecha_fin=texto_a_fecha(fila["fecha_fin"]),
        modalidad=ModalidadAlquiler(fila["modalidad"]),
        tarifa=fila["tarifa"],
        valor_liquidado=fila["valor_liquidado"],
        observaciones=fila["observaciones"],
        cobrado=int(fila["cobrado"]),
        horas_uso=fila["horas_uso"],
    )


def _fila_a_ingreso(fila: sqlite3.Row) -> Ingreso:
    return Ingreso(
        id=fila["id"],
        planta_id=fila["planta_id"],
        tipo=TipoIngreso(fila["tipo"]),
        alquiler_id=fila["alquiler_id"],
        cliente_id=fila["cliente_id"],
        cliente_nombre=fila["cliente_nombre"],
        datos=DatosIngreso(
            texto_a_fecha_obligatoria(fila["fecha"]),
            fila["descripcion"],
            fila["valor"],
            fila["numero_documento"],
        ),
        anulado=bool(fila["anulado"]),
        motivo_anulacion=fila["motivo_anulacion"],
    )
