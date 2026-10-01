"""
Pruebas de integración: PlantaService + repositorios SQLite reales.

Ruta: tests/integration/test_planta_service_sqlite.py

Verifican que las tres capas encajen: reglas de negocio, traducción de
tipos, transacciones y restricciones del esquema trabajando juntas.
"""

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from src.business.exceptions import PersistenciaError, ValidacionError
from src.business.models.estado_planta import EstadoPlanta as E
from src.business.models.planta import DatosPlanta, TipoCombustible
from src.business.services.consecutivo_service import ConsecutivoService
from src.business.services.planta_service import PlantaService
from src.config import settings
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.repositories.sqlite_unidad_de_trabajo import (
    SqliteUnidadDeTrabajo,
    crear_fabrica_uow,
)
from src.shared.paths import get_resource_path

HOY = date(2026, 9, 30)


def _datos(marca: str = "Cummins", serie: str | None = None) -> DatosPlanta:
    return DatosPlanta(marca=marca, potencia_kva=100, numero_serie=serie)


@pytest.fixture
def db(tmp_path: Path) -> DatabaseManager:
    manager = DatabaseManager(tmp_path / "integracion.db", timeout=0.2)
    manager.initialize_schema(get_resource_path(settings.SCHEMA_RELATIVE_PATH))
    return manager


@pytest.fixture
def servicio(db: DatabaseManager) -> PlantaService:
    return PlantaService(crear_fabrica_uow(db), ConsecutivoService(), hoy=lambda: HOY)


def _verificar_invariante_de_consecutivos(db: DatabaseManager) -> None:
    """
    Regla que debe cumplirse SIEMPRE: cada planta en operación tiene exactamente
    un registro vigente con su mismo número; las demás no tienen ninguno.
    """
    with db.connection() as conn:
        plantas = conn.execute("SELECT id, numero_consecutivo FROM plantas").fetchall()
        for p in plantas:
            vigentes = conn.execute(
                "SELECT numero FROM historial_consecutivos "
                "WHERE planta_id = ? AND fecha_liberacion IS NULL",
                (p["id"],),
            ).fetchall()
            if p["numero_consecutivo"] is None:
                assert vigentes == []
            else:
                assert [v["numero"] for v in vigentes] == [p["numero_consecutivo"]]


# --- Persistencia de datos ---------------------------------------------------


def test_todos_los_campos_se_guardan_y_recuperan_intactos(servicio: PlantaService) -> None:
    datos = DatosPlanta(
        marca="Cummins",
        potencia_kva=125.5,
        modelo="C125D6",
        numero_serie="SN-0001",
        potencia_kw=100.0,
        voltaje="120/240 V",
        fases=3,
        tipo_combustible=TipoCombustible.DIESEL,
        capacidad_tanque_gal=55.0,
        fecha_adquisicion=date(2024, 5, 20),
        valor_compra=85_000_000,
        horometro_inicial=1200,
        observaciones="Incluye cabina insonorizada",
    )
    registrada = servicio.registrar(datos)
    leida = servicio.obtener(registrada.id)

    assert leida.datos == datos  # Ida y vuelta sin perder nada
    assert leida.estado is E.DISPONIBLE
    assert leida.numero_consecutivo == 1


def test_actualizar_datos_no_altera_estado_ni_numero(servicio: PlantaService) -> None:
    planta = servicio.registrar(_datos())
    servicio.cambiar_estado(planta.id, E.ALQUILADA)
    actualizada = servicio.actualizar_datos(planta.id, _datos(marca="Cummins Power"))

    assert actualizada.datos.marca == "Cummins Power"
    assert actualizada.estado is E.ALQUILADA
    assert actualizada.numero_consecutivo == 1


def test_serie_duplicada_sin_importar_mayusculas(servicio: PlantaService) -> None:
    servicio.registrar(_datos(serie="abc-123"))
    with pytest.raises(ValidacionError):
        servicio.registrar(_datos(serie="ABC-123"))


# --- Consecutivos ------------------------------------------------------------


def test_ciclo_completo_de_consecutivos(servicio: PlantaService, db: DatabaseManager) -> None:
    p1 = servicio.registrar(_datos())  # 1
    p2 = servicio.registrar(_datos())  # 2
    servicio.cambiar_estado(p1.id, E.VENDIDA, motivo="Venta")  # libera 1
    p3 = servicio.registrar(_datos())  # reutiliza 1
    servicio.cambiar_estado(p2.id, E.RETIRADA, motivo="Bodega")  # libera 2
    reactivada = servicio.cambiar_estado(p2.id, E.DISPONIBLE)  # recupera 2

    assert p3.numero_consecutivo == 1
    assert reactivada.numero_consecutivo == 2
    assert [r.planta_id for r in servicio.quienes_tuvieron_numero(1)] == [p1.id, p3.id]
    _verificar_invariante_de_consecutivos(db)


def test_historial_completo_de_una_planta(servicio: PlantaService) -> None:
    planta = servicio.registrar(_datos())
    servicio.cambiar_estado(planta.id, E.RETIRADA, motivo="Sin demanda")
    servicio.cambiar_estado(planta.id, E.DISPONIBLE)

    cambios, consecutivos = servicio.historial(planta.id)

    assert [c.estado_nuevo for c in cambios] == [E.DISPONIBLE, E.RETIRADA, E.DISPONIBLE]
    assert cambios[1].motivo == "Sin demanda"
    assert len(consecutivos) == 2
    assert consecutivos[0].motivo_liberacion == "Sin demanda"
    assert consecutivos[1].vigente


# --- Consultas ---------------------------------------------------------------


def test_listar_filtra_y_ordena(servicio: PlantaService) -> None:
    p1 = servicio.registrar(_datos(marca="Cummins"))
    servicio.registrar(_datos(marca="Perkins"))
    servicio.cambiar_estado(p1.id, E.DADA_DE_BAJA, motivo="Irreparable")

    assert [p.datos.marca for p in servicio.listar()] == ["Perkins"]
    todas = servicio.listar(incluir_fuera_de_operacion=True)
    assert [p.datos.marca for p in todas] == ["Perkins", "Cummins"]  # Sin número al final


def test_busqueda_trata_comodines_como_texto(servicio: PlantaService) -> None:
    servicio.registrar(_datos(marca="Cummins"))
    servicio.registrar(_datos(marca="Planta 50% carga"))
    assert len(servicio.listar(texto="%")) == 1
    assert len(servicio.listar(texto="cumm")) == 1


# --- Robustez ----------------------------------------------------------------


def test_rollback_real_ante_error_a_mitad_de_operacion(
    servicio: PlantaService, db: DatabaseManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fallar(*_args: object) -> None:
        raise RuntimeError("Falla simulada")

    monkeypatch.setattr(
        "src.infrastructure.repositories.sqlite_historial_estado_repository."
        "SqliteHistorialEstadoRepository.registrar",
        fallar,
    )
    with pytest.raises(RuntimeError):
        servicio.registrar(_datos())

    with db.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM plantas").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM historial_consecutivos").fetchone()[0] == 0


def test_el_esquema_respalda_las_reglas_aunque_se_salte_el_servicio(
    servicio: PlantaService, db: DatabaseManager
) -> None:
    """Defensa en profundidad: si un error de código ignora las reglas, SQLite lo frena."""
    planta = servicio.registrar(_datos())
    with pytest.raises(PersistenciaError, match="integridad"), SqliteUnidadDeTrabajo(db) as uow:
        uow.plantas.actualizar_estado(planta.id, E.VENDIDA, numero=1)

    assert servicio.obtener(planta.id).estado is E.DISPONIBLE


def test_base_de_datos_bloqueada_se_informa_con_mensaje_claro(
    servicio: PlantaService, db: DatabaseManager
) -> None:
    bloqueador = sqlite3.connect(db.db_path, isolation_level=None)
    try:
        bloqueador.execute("BEGIN IMMEDIATE;")  # Otro proceso "ocupa" la escritura
        with pytest.raises(PersistenciaError, match="ocupada"):
            servicio.registrar(_datos())
    finally:
        bloqueador.execute("ROLLBACK;")
        bloqueador.close()

    assert servicio.registrar(_datos()).numero_consecutivo == 1  # Luego funciona normal
