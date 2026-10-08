"""
El formulario ofrece Gas solo como "(histórico)" al editar una planta que ya lo tiene.

Ruta: tests/ui/test_combustible_en_formulario.py
"""

from datetime import date

import pytest
from PySide6.QtWidgets import QApplication

from src.business.models.hoja_vida import DatosEmpresa
from src.business.models.planta import TipoCombustible
from src.business.services.consecutivo_service import ConsecutivoService
from src.business.services.hoja_vida_service import HojaVidaService
from src.business.services.planta_service import PlantaService
from src.infrastructure.reports.pdf_hoja_vida import GeneradorPdfHojaVida
from src.presentation.controllers.inventario_controller import InventarioController
from src.presentation.views.equipos.inventario_view import InventarioView
from tests.unit.fakes import AlmacenFake, FakeUnidadDeTrabajo


@pytest.fixture
def controlador(qapp: QApplication) -> InventarioController:
    almacen = AlmacenFake()
    fabrica = lambda: FakeUnidadDeTrabajo(almacen)  # noqa: E731
    servicio = PlantaService(fabrica, ConsecutivoService(), lambda: date(2026, 9, 30))
    hojas = HojaVidaService(
        fabrica, GeneradorPdfHojaVida(), lambda: DatosEmpresa("Prueba"), "0.4.0"
    )
    return InventarioController(servicio, hojas, InventarioView())


def _opciones_combustible(controlador: InventarioController, actual: TipoCombustible | None):
    dialogo = controlador._crear_formulario("t", "x", "y", combustible_actual=actual)
    combo = dialogo._combustible
    return [(combo.itemText(i), combo.itemData(i)) for i in range(combo.count())]


def test_registro_nuevo_no_ofrece_gas(controlador: InventarioController) -> None:
    claves = [clave for _texto, clave in _opciones_combustible(controlador, None)]
    assert claves == [None, "DIESEL", "GASOLINA"]


def test_editar_planta_con_gas_la_muestra_como_historico(
    controlador: InventarioController,
) -> None:
    opciones = _opciones_combustible(controlador, TipoCombustible.GAS)
    assert opciones[-1] == ("Gas (histórico)", "GAS")


def test_voltaje_sugerido_es_110_220(controlador: InventarioController) -> None:
    dialogo = controlador._crear_formulario("t", "x", "y")
    combo = dialogo._voltaje
    assert [combo.itemText(i) for i in range(combo.count())] == ["110/220 V"]
    assert combo.lineEdit().placeholderText() == "Ej. 110/220 V"
