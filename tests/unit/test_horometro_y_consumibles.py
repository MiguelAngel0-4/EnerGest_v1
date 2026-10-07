"""
Pruebas unitarias de los ajustes de la validación del MVP 1:
horómetro al alquilar y datos de filtros y aceite.

Ruta: tests/unit/test_horometro_y_consumibles.py
"""

from dataclasses import replace
from datetime import date

import pytest

from src.business.exceptions import ValidacionError
from src.business.models.estado_planta import EstadoPlanta as E
from src.business.models.planta import DatosPlanta, TipoAceite
from src.business.services.consecutivo_service import ConsecutivoService
from src.business.services.planta_service import PlantaService
from src.business.validators.planta_validator import normalizar_datos, validar_datos
from tests.unit.fakes import AlmacenFake, FakeUnidadDeTrabajo

HOY = date(2026, 9, 30)


@pytest.fixture
def servicio() -> PlantaService:
    almacen = AlmacenFake()
    return PlantaService(lambda: FakeUnidadDeTrabajo(almacen), ConsecutivoService(), lambda: HOY)


def _registrar(servicio: PlantaService, horometro_inicial: int = 1000) -> int:
    datos = DatosPlanta(marca="Cummins", potencia_kva=100, horometro_inicial=horometro_inicial)
    return servicio.registrar(datos).id


# --- Horómetro ---------------------------------------------------------------


def test_solo_alquilar_exige_horometro() -> None:
    assert {e for e in E if e.requiere_horometro} == {E.ALQUILADA}


def test_alquilar_sin_lectura_es_rechazado(servicio: PlantaService) -> None:
    planta_id = _registrar(servicio)
    with pytest.raises(ValidacionError) as error:
        servicio.cambiar_estado(planta_id, E.ALQUILADA)
    assert "horometro" in error.value.errores


def test_lectura_menor_que_la_ultima_es_rechazada(servicio: PlantaService) -> None:
    planta_id = _registrar(servicio, horometro_inicial=1000)
    with pytest.raises(ValidacionError, match="no puede ser menor"):
        servicio.cambiar_estado(planta_id, E.ALQUILADA, horometro=800)


def test_lectura_negativa_es_rechazada(servicio: PlantaService) -> None:
    planta_id = _registrar(servicio, horometro_inicial=0)
    with pytest.raises(ValidacionError):
        servicio.cambiar_estado(planta_id, E.ALQUILADA, horometro=-5)


def test_ciclo_de_alquiler_actualiza_el_horometro_actual(servicio: PlantaService) -> None:
    planta_id = _registrar(servicio, horometro_inicial=1000)

    salida = servicio.cambiar_estado(planta_id, E.ALQUILADA, horometro=1020)
    regreso = servicio.cambiar_estado(planta_id, E.DISPONIBLE, horometro=1185)

    assert salida.horometro_actual == 1020
    assert regreso.horometro_actual == 1185
    cambios, _ = servicio.historial(planta_id)
    assert [c.horometro for c in cambios] == [None, 1020, 1185]


def test_regresar_del_alquiler_sin_lectura_es_permitido(servicio: PlantaService) -> None:
    planta_id = _registrar(servicio, horometro_inicial=1000)
    servicio.cambiar_estado(planta_id, E.ALQUILADA, horometro=1000)  # Igual a la última: válido
    devuelta = servicio.cambiar_estado(planta_id, E.DISPONIBLE)
    assert devuelta.horometro_actual == 1000


def test_horometro_actual_inicial_es_el_del_registro(servicio: PlantaService) -> None:
    planta_id = _registrar(servicio, horometro_inicial=2500)
    assert servicio.obtener(planta_id).horometro_actual == 2500


# --- Filtros y aceite --------------------------------------------------------


def test_etiquetas_de_tipo_de_aceite() -> None:
    assert [t.etiqueta for t in TipoAceite] == ["15W-40", "25W-60"]


def test_normalizar_limpia_referencias_de_filtros() -> None:
    datos = DatosPlanta(
        marca="Cummins", potencia_kva=50, filtro_aceite="  LF3000 ", filtro_aire="   "
    )
    limpio = normalizar_datos(datos)
    assert limpio.filtro_aceite == "LF3000"
    assert limpio.filtro_aire is None


def test_cantidad_de_aceite_debe_ser_positiva() -> None:
    datos = DatosPlanta(marca="Cummins", potencia_kva=50)
    assert "cantidad_aceite_gal" in validar_datos(replace(datos, cantidad_aceite_gal=0), HOY)
    assert validar_datos(replace(datos, cantidad_aceite_gal=2.5), HOY) == {}


def test_registrar_conserva_los_datos_de_consumibles(servicio: PlantaService) -> None:
    datos = DatosPlanta(
        marca="Perkins",
        potencia_kva=60,
        filtro_aceite="LF3000",
        filtro_combustible="FS1280",
        filtro_agua="WF2071",
        filtro_aire="P181052",
        cantidad_aceite_gal=2.5,
        tipo_aceite=TipoAceite.SAE_15W40,
    )
    assert servicio.registrar(datos).datos == datos
