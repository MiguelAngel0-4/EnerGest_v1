"""
Pruebas de integración de filtros, aceite y horómetro sobre SQLite real.

Ruta: tests/integration/test_consumibles_horometro_sqlite.py
"""

from datetime import date
from pathlib import Path

import pytest

from src.business.exceptions import ValidacionError
from src.business.models.estado_planta import EstadoPlanta as E
from src.business.models.planta import DatosPlanta, TipoAceite
from src.business.services.consecutivo_service import ConsecutivoService
from src.business.services.planta_service import PlantaService
from src.config import settings
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.repositories.sqlite_unidad_de_trabajo import crear_fabrica_uow
from src.shared.paths import get_resource_path


def _datos(horometro_inicial: int) -> DatosPlanta:
    return DatosPlanta(marca="Cummins", potencia_kva=50, horometro_inicial=horometro_inicial)


@pytest.fixture
def servicio(tmp_path: Path) -> PlantaService:
    db = DatabaseManager(tmp_path / "v2.db")
    db.initialize_schema(get_resource_path(settings.SCHEMA_RELATIVE_PATH))
    return PlantaService(crear_fabrica_uow(db), ConsecutivoService(), lambda: date(2026, 9, 30))


def test_consumibles_se_guardan_y_recuperan_intactos(servicio: PlantaService) -> None:
    datos = DatosPlanta(
        marca="Perkins",
        potencia_kva=60,
        filtro_aceite="Fleetguard LF3000",
        filtro_combustible="Fleetguard FS1280",
        filtro_agua="Fleetguard WF2071",
        filtro_aire="Donaldson P181052",
        cantidad_aceite_gal=2.5,
        tipo_aceite=TipoAceite.SAE_25W60,
    )
    planta = servicio.registrar(datos)
    assert servicio.obtener(planta.id).datos == datos


def test_horometro_actual_se_calcula_desde_el_historial(servicio: PlantaService) -> None:
    planta = servicio.registrar(_datos(horometro_inicial=900))
    servicio.cambiar_estado(planta.id, E.ALQUILADA, horometro=950)
    servicio.cambiar_estado(planta.id, E.DISPONIBLE, horometro=1130)

    assert servicio.obtener(planta.id).horometro_actual == 1130
    assert servicio.listar()[0].horometro_actual == 1130
    cambios, _ = servicio.historial(planta.id)
    assert [c.horometro for c in cambios] == [None, 950, 1130]


def test_lectura_menor_es_rechazada_y_no_se_guarda_nada(servicio: PlantaService) -> None:
    planta = servicio.registrar(_datos(horometro_inicial=900))
    with pytest.raises(ValidacionError):
        servicio.cambiar_estado(planta.id, E.ALQUILADA, horometro=100)

    actual = servicio.obtener(planta.id)
    assert actual.estado is E.DISPONIBLE
    assert actual.horometro_actual == 900
