"""
Pruebas de la regla "Gas solo como dato histórico".

Ruta: tests/unit/test_combustible_historico.py

Decisión de la empresa: las plantas que ya tienen Gas lo conservan,
pero no puede asignarse en registros nuevos ni a otras plantas.
"""

from dataclasses import replace
from datetime import date

import pytest

from src.business.exceptions import ValidacionError
from src.business.models.estado_planta import EstadoPlanta
from src.business.models.planta import DatosPlanta, TipoCombustible
from src.business.services.consecutivo_service import ConsecutivoService
from src.business.services.planta_service import PlantaService
from tests.unit.fakes import AlmacenFake, FakeUnidadDeTrabajo

DIESEL = DatosPlanta(marca="Cummins", potencia_kva=50, tipo_combustible=TipoCombustible.DIESEL)


@pytest.fixture
def almacen() -> AlmacenFake:
    return AlmacenFake()


@pytest.fixture
def servicio(almacen: AlmacenFake) -> PlantaService:
    return PlantaService(
        lambda: FakeUnidadDeTrabajo(almacen), ConsecutivoService(), lambda: date(2026, 9, 30)
    )


def _planta_historica_con_gas(almacen: AlmacenFake) -> int:
    """Simula una planta registrada ANTES de retirar el Gas (sin pasar por el servicio)."""
    with FakeUnidadDeTrabajo(almacen) as uow:
        datos = replace(DIESEL, tipo_combustible=TipoCombustible.GAS)
        return uow.plantas.insertar(datos, 1, EstadoPlanta.DISPONIBLE)


def test_solo_diesel_y_gasolina_estan_vigentes() -> None:
    assert {c for c in TipoCombustible if c.vigente} == {
        TipoCombustible.DIESEL,
        TipoCombustible.GASOLINA,
    }


def test_registrar_con_gas_es_rechazado(servicio: PlantaService) -> None:
    with pytest.raises(ValidacionError) as error:
        servicio.registrar(replace(DIESEL, tipo_combustible=TipoCombustible.GAS))
    assert "tipo_combustible" in error.value.errores


def test_cambiar_una_planta_a_gas_es_rechazado(servicio: PlantaService) -> None:
    planta = servicio.registrar(DIESEL)
    with pytest.raises(ValidacionError):
        servicio.actualizar_datos(planta.id, replace(DIESEL, tipo_combustible=TipoCombustible.GAS))


def test_planta_historica_conserva_gas_al_editar_otros_datos(
    servicio: PlantaService, almacen: AlmacenFake
) -> None:
    planta_id = _planta_historica_con_gas(almacen)
    actual = servicio.obtener(planta_id).datos

    editada = servicio.actualizar_datos(planta_id, replace(actual, modelo="C50D6"))

    assert editada.datos.tipo_combustible is TipoCombustible.GAS
    assert editada.datos.modelo == "C50D6"


def test_planta_historica_puede_pasar_a_un_combustible_vigente(
    servicio: PlantaService, almacen: AlmacenFake
) -> None:
    planta_id = _planta_historica_con_gas(almacen)
    actual = servicio.obtener(planta_id).datos
    editada = servicio.actualizar_datos(
        planta_id, replace(actual, tipo_combustible=TipoCombustible.DIESEL)
    )
    assert editada.datos.tipo_combustible is TipoCombustible.DIESEL
