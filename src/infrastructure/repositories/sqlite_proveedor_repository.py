"""
Repositorios SQLite de proveedores y categorías de gasto.

Ruta: src/infrastructure/repositories/sqlite_proveedor_repository.py
"""

import sqlite3

from src.business.models.gasto import CategoriaGasto, Proveedor


class SqliteProveedorRepository:
    """Acceso a la tabla proveedores."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def insertar(self, nombre: str, nit: str | None, telefono: str | None) -> int:
        cursor = self._conn.execute(
            "INSERT INTO proveedores (nombre, nit, telefono) VALUES (?, ?, ?)",
            (nombre, nit, telefono),
        )
        return int(cursor.lastrowid)  # type: ignore[arg-type]

    def obtener(self, proveedor_id: int) -> Proveedor | None:
        fila = self._conn.execute(
            "SELECT * FROM proveedores WHERE id = ?", (proveedor_id,)
        ).fetchone()
        return _fila_a_proveedor(fila) if fila is not None else None

    def listar(self) -> list[Proveedor]:
        filas = self._conn.execute(
            "SELECT * FROM proveedores WHERE activo = 1 ORDER BY nombre COLLATE NOCASE"
        ).fetchall()
        return [_fila_a_proveedor(f) for f in filas]

    def existe_nombre(self, nombre: str) -> bool:
        return self._existe("trim(nombre) = trim(?) COLLATE NOCASE", nombre)

    def existe_nit(self, nit: str) -> bool:
        return self._existe("trim(nit) = trim(?) COLLATE NOCASE", nit)

    def _existe(self, condicion: str, valor: str) -> bool:
        fila = self._conn.execute(
            f"SELECT 1 FROM proveedores WHERE {condicion} LIMIT 1", (valor,)
        ).fetchone()
        return fila is not None


class SqliteCategoriaRepository:
    """Acceso al catálogo categorias_gasto."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def obtener(self, categoria_id: int) -> CategoriaGasto | None:
        fila = self._conn.execute(
            "SELECT * FROM categorias_gasto WHERE id = ?", (categoria_id,)
        ).fetchone()
        return _fila_a_categoria(fila) if fila is not None else None

    def listar(self) -> list[CategoriaGasto]:
        filas = self._conn.execute(
            "SELECT * FROM categorias_gasto WHERE activo = 1 ORDER BY id"
        ).fetchall()
        return [_fila_a_categoria(f) for f in filas]


def _fila_a_proveedor(fila: sqlite3.Row) -> Proveedor:
    return Proveedor(
        id=fila["id"],
        nombre=fila["nombre"],
        nit=fila["nit"],
        telefono=fila["telefono"],
        activo=bool(fila["activo"]),
    )


def _fila_a_categoria(fila: sqlite3.Row) -> CategoriaGasto:
    return CategoriaGasto(id=fila["id"], nombre=fila["nombre"], activo=bool(fila["activo"]))
