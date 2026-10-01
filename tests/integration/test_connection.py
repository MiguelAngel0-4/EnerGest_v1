"""
Pruebas de integración de la base técnica de datos.

Ruta: tests/integration/test_connection.py

Verifican que los cimientos se comporten como se diseñaron:
esquema, llaves foráneas, atomicidad y reglas CHECK.
Cada prueba usa una base de datos nueva en una carpeta temporal.
"""

from pathlib import Path

import pytest

from src.config import settings
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.exceptions import DatabaseIntegrityError
from src.shared.paths import get_resource_path

TABLAS_ESPERADAS: set[str] = {
    "plantas",
    "historial_consecutivos",
    "historial_estados",
    "proveedores",
    "categorias_gasto",
    "facturas_proveedor",
    "mantenimientos",
    "gastos",
}


@pytest.fixture
def db(tmp_path: Path) -> DatabaseManager:
    """Base de datos limpia con el esquema recién creado."""
    manager = DatabaseManager(tmp_path / "prueba.db")
    manager.initialize_schema(get_resource_path(settings.SCHEMA_RELATIVE_PATH))
    return manager


def _insertar_planta(conn, numero: int | None = 1, estado: str = "DISPONIBLE") -> int:
    """Inserta una planta mínima válida y devuelve su id."""
    cursor = conn.execute(
        "INSERT INTO plantas (numero_consecutivo, estado, marca, potencia_kva) "
        "VALUES (?, ?, 'Cummins', 50)",
        (numero, estado),
    )
    return int(cursor.lastrowid)


def test_esquema_crea_todas_las_tablas_y_registra_version(db: DatabaseManager) -> None:
    with db.connection() as conn:
        tablas = {
            fila["name"]
            for fila in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        version = conn.execute("PRAGMA user_version;").fetchone()[0]

    assert TABLAS_ESPERADAS <= tablas
    assert version == settings.SCHEMA_VERSION


def test_inicializar_dos_veces_no_duplica_datos(db: DatabaseManager) -> None:
    db.initialize_schema(get_resource_path(settings.SCHEMA_RELATIVE_PATH))
    with db.connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM categorias_gasto").fetchone()[0]
    assert total == 5


def test_llaves_foraneas_estan_activas(db: DatabaseManager) -> None:
    with pytest.raises(DatabaseIntegrityError):
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO gastos (planta_id, categoria_id, fecha, descripcion, valor_total) "
                "VALUES (999, 1, '2026-09-29', 'Filtro', 45000)"
            )


def test_transaccion_hace_rollback_ante_error_de_negocio(db: DatabaseManager) -> None:
    with pytest.raises(ValueError):
        with db.transaction() as conn:
            conn.execute("INSERT INTO proveedores (nombre) VALUES ('Repuestos del Valle')")
            raise ValueError("Falla simulada en la lógica de negocio")

    with db.connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM proveedores").fetchone()[0]
    assert total == 0


def test_planta_vendida_no_puede_conservar_numero(db: DatabaseManager) -> None:
    with pytest.raises(DatabaseIntegrityError):
        with db.transaction() as conn:
            _insertar_planta(conn, numero=1, estado="VENDIDA")


def test_planta_activa_debe_tener_numero(db: DatabaseManager) -> None:
    with pytest.raises(DatabaseIntegrityError):
        with db.transaction() as conn:
            _insertar_planta(conn, numero=None, estado="DISPONIBLE")


@pytest.mark.parametrize("fecha_invalida", ["29/09/2026", "2026-02-30", "ayer"])
def test_fechas_mal_escritas_son_rechazadas(db: DatabaseManager, fecha_invalida: str) -> None:
    with pytest.raises(DatabaseIntegrityError):
        with db.transaction() as conn:
            planta_id = _insertar_planta(conn)
            conn.execute(
                "INSERT INTO gastos (planta_id, categoria_id, fecha, descripcion, valor_total) "
                "VALUES (?, 1, ?, 'Aceite 15W40', 120000)",
                (planta_id, fecha_invalida),
            )


def test_gasto_sin_factura_es_valido(db: DatabaseManager) -> None:
    with db.transaction() as conn:
        planta_id = _insertar_planta(conn)
        conn.execute(
            "INSERT INTO gastos (planta_id, categoria_id, fecha, descripcion, valor_total) "
            "VALUES (?, 4, '2026-09-29', 'Mano de obra técnico independiente', 80000)",
            (planta_id,),
        )

    with db.connection() as conn:
        fila = conn.execute("SELECT factura_id, valor_total FROM gastos").fetchone()
    assert fila["factura_id"] is None
    assert fila["valor_total"] == 80000


def test_numero_de_factura_no_se_repite_para_el_mismo_proveedor(db: DatabaseManager) -> None:
    with pytest.raises(DatabaseIntegrityError):
        with db.transaction() as conn:
            conn.execute("INSERT INTO proveedores (id, nombre) VALUES (1, 'Filtros SAS')")
            for _ in range(2):
                conn.execute(
                    "INSERT INTO facturas_proveedor "
                    "(proveedor_id, numero_factura, fecha_factura, valor_total) "
                    "VALUES (1, 'FE-001', '2026-09-29', 300000)"
                )


def test_tabla_strict_rechaza_tipos_incorrectos(db: DatabaseManager) -> None:
    with pytest.raises(DatabaseIntegrityError):
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO plantas (numero_consecutivo, marca, potencia_kva) "
                "VALUES ('uno', 'Cummins', 50)"
            )
