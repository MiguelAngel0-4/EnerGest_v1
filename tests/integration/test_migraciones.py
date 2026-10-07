"""
Pruebas del sistema de migraciones y respaldos.

Ruta: tests/integration/test_migraciones.py

Protegen el escenario más delicado del proyecto: actualizar el programa
en un equipo donde ya existe una base de datos con información real.
"""

import shutil
import sqlite3
from pathlib import Path

import pytest

from src.config import settings
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.exceptions import SchemaInitializationError
from src.shared.paths import get_resource_path

SCHEMA = get_resource_path(settings.SCHEMA_RELATIVE_PATH)
MIGRACIONES = SCHEMA.parent / "migrations"


def _crear_base_version_1(ruta: Path) -> None:
    """Simula una base creada con la versión 0.2.0 del programa, con una planta."""
    conn = sqlite3.connect(ruta)
    conn.executescript(SCHEMA.read_text(encoding="utf-8") + "\nPRAGMA user_version = 1;")
    conn.execute(
        "INSERT INTO plantas (numero_consecutivo, marca, potencia_kva) VALUES (1, 'Cummins', 50)"
    )
    conn.commit()
    conn.close()


def _version(ruta: Path) -> int:
    conn = sqlite3.connect(ruta)
    try:
        return int(conn.execute("PRAGMA user_version").fetchone()[0])
    finally:
        conn.close()


def _columnas(ruta: Path, tabla: str) -> set[str]:
    conn = sqlite3.connect(ruta)
    try:
        return {fila[1] for fila in conn.execute(f"PRAGMA table_info({tabla})")}
    finally:
        conn.close()


def test_schema_version_coincide_con_la_ultima_migracion() -> None:
    """Si alguien agrega una migración y olvida subir SCHEMA_VERSION, esta prueba falla."""
    numeros = [int(f.name[:3]) for f in MIGRACIONES.glob("[0-9][0-9][0-9]_*.sql")]
    assert max(numeros, default=1) == settings.SCHEMA_VERSION


def test_base_nueva_queda_en_la_ultima_version_sin_respaldo(tmp_path: Path) -> None:
    ruta = tmp_path / "nueva.db"
    DatabaseManager(ruta).initialize_schema(SCHEMA)

    assert _version(ruta) == settings.SCHEMA_VERSION
    assert {"filtro_aceite", "tipo_aceite", "cantidad_aceite_gal"} <= _columnas(ruta, "plantas")
    assert "horometro" in _columnas(ruta, "historial_estados")
    assert not (tmp_path / "respaldos").exists()  # Nada que respaldar en una base vacía


def test_base_existente_migra_conservando_datos_y_con_respaldo(tmp_path: Path) -> None:
    ruta = tmp_path / "empresa.db"
    _crear_base_version_1(ruta)

    DatabaseManager(ruta).initialize_schema(SCHEMA)

    assert _version(ruta) == settings.SCHEMA_VERSION
    conn = sqlite3.connect(ruta)
    assert conn.execute("SELECT marca, filtro_aceite FROM plantas").fetchall() == [
        ("Cummins", None)
    ]
    conn.close()

    respaldos = list((tmp_path / "respaldos").glob("empresa_v1_*.db"))
    assert len(respaldos) == 1
    assert _version(respaldos[0]) == 1  # El respaldo es la base ANTES de migrar


def test_migrar_dos_veces_no_hace_nada_la_segunda(tmp_path: Path) -> None:
    ruta = tmp_path / "empresa.db"
    _crear_base_version_1(ruta)
    db = DatabaseManager(ruta)
    db.initialize_schema(SCHEMA)
    db.initialize_schema(SCHEMA)
    assert len(list((tmp_path / "respaldos").glob("*.db"))) == 1


def test_migracion_fallida_deja_la_base_intacta(tmp_path: Path) -> None:
    ruta = tmp_path / "empresa.db"
    _crear_base_version_1(ruta)
    rotas = tmp_path / "migraciones_rotas"
    rotas.mkdir()
    # La primera sentencia es válida; la segunda falla. Nada debe quedar aplicado.
    (rotas / "002_rota.sql").write_text(
        "ALTER TABLE plantas ADD COLUMN columna_nueva TEXT;\nESTO NO ES SQL;", encoding="utf-8"
    )

    with pytest.raises(SchemaInitializationError, match="quedó sin cambios"):
        DatabaseManager(ruta).initialize_schema(SCHEMA, migrations_dir=rotas)

    assert _version(ruta) == 1
    assert "columna_nueva" not in _columnas(ruta, "plantas")


def test_base_mas_nueva_que_el_programa_es_rechazada(tmp_path: Path) -> None:
    ruta = tmp_path / "futura.db"
    DatabaseManager(ruta).initialize_schema(SCHEMA)
    conn = sqlite3.connect(ruta)
    conn.execute(f"PRAGMA user_version = {settings.SCHEMA_VERSION + 1}")
    conn.close()

    with pytest.raises(SchemaInitializationError, match="versión más reciente"):
        DatabaseManager(ruta).initialize_schema(SCHEMA)


def test_olvidar_actualizar_schema_version_detiene_el_inicio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    carpeta = tmp_path / "migraciones"
    shutil.copytree(MIGRACIONES, carpeta)
    (carpeta / f"{settings.SCHEMA_VERSION + 1:03d}_nueva.sql").write_text("SELECT 1;")

    with pytest.raises(SchemaInitializationError, match="SCHEMA_VERSION"):
        DatabaseManager(tmp_path / "x.db").initialize_schema(SCHEMA, migrations_dir=carpeta)


def test_respaldo_manual_es_una_copia_completa(tmp_path: Path) -> None:
    ruta = tmp_path / "empresa.db"
    db = DatabaseManager(ruta)
    db.initialize_schema(SCHEMA)

    respaldo = db.backup(tmp_path / "copias")

    conn = sqlite3.connect(respaldo)
    total = conn.execute("SELECT COUNT(*) FROM categorias_gasto").fetchone()[0]
    conn.close()
    assert total == 5
    assert _version(respaldo) == settings.SCHEMA_VERSION
