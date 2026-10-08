"""
Pruebas de interfaz del módulo de gastos (ficha, formularios y pestaña).

Ruta: tests/ui/test_gastos_ui.py
"""

from datetime import date

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from src.business.models.planta import DatosPlanta, TipoAceite
from src.business.services.consecutivo_service import ConsecutivoService
from src.business.services.gasto_service import GastoService
from src.business.services.planta_service import PlantaService
from src.presentation.controllers.ficha_controller import FichaPlantaController
from src.presentation.dialogs.ficha_planta_dialog import FichaPlantaDialog
from src.presentation.dialogs.gasto_dialogs import (
    NuevaFacturaDialog,
    OpcionFactura,
    RegistrarGastoDialog,
)
from src.presentation.widgets.gastos_widget import FilaGasto, GastosWidget
from tests.ui.conftest import escribir_como_usuario
from tests.unit.fakes import AlmacenFake, FakeUnidadDeTrabajo

CATEGORIAS = [("Filtros", 1), ("Repuestos", 2), ("Mano de obra", 4)]


def _dialogo_gasto() -> RegistrarGastoDialog:
    dialogo = RegistrarGastoDialog(
        "PE-001 · Cummins",
        CATEGORIAS,
        {1: ["Filtro de aceite LF3000", "Filtro de aire P181052"]},
        ["Unidad", "Galón"],
    )
    dialogo.show()
    return dialogo


def _emitidos(dialogo: QWidget) -> list[dict]:
    lista: list[dict] = []
    dialogo.guardar_solicitado.connect(lista.append)  # type: ignore[attr-defined]
    return lista


# --- Formulario de gasto -------------------------------------------------------


def test_valor_y_cantidad_aceptan_escritura_real(qapp: QApplication) -> None:
    dialogo = _dialogo_gasto()
    dialogo._cantidad.clear()
    escribir_como_usuario(dialogo._cantidad, "2,5")
    escribir_como_usuario(dialogo._valor, "45000")
    valores = dialogo.valores()
    assert (valores["cantidad"], valores["valor_total"]) == (2.5, 45_000)


def test_con_factura_sin_elegir_muestra_error_y_no_envia(qapp: QApplication) -> None:
    dialogo = _dialogo_gasto()
    emitidos = _emitidos(dialogo)
    dialogo._al_guardar()
    assert emitidos == []
    assert dialogo._campos["factura_id"][1].isVisible()


def test_sin_factura_envia_factura_vacia(qapp: QApplication) -> None:
    dialogo = _dialogo_gasto()
    emitidos = _emitidos(dialogo)
    dialogo._sin_factura.setChecked(True)
    dialogo._al_guardar()
    assert emitidos[0]["factura_id"] is None
    assert not dialogo._factura.isEnabled()


def test_factura_seleccionada_muestra_su_saldo(qapp: QApplication) -> None:
    dialogo = _dialogo_gasto()
    dialogo.set_facturas(
        [OpcionFactura(7, "FE-0042 · Filtros del Valle", "$ 120.000")], seleccionar=7
    )
    assert dialogo.valores()["factura_id"] == 7
    assert "$ 120.000" in dialogo._saldo.text()


def test_sugerencias_cambian_con_la_categoria(qapp: QApplication) -> None:
    dialogo = _dialogo_gasto()
    sugerencias = [dialogo._descripcion.itemText(i) for i in range(dialogo._descripcion.count())]
    assert sugerencias == ["Filtro de aceite LF3000", "Filtro de aire P181052"]

    dialogo._categoria.setCurrentIndex(2)  # Mano de obra: sin sugerencias
    assert dialogo._descripcion.count() == 0


def test_nueva_factura_exige_proveedor(qapp: QApplication) -> None:
    dialogo = NuevaFacturaDialog()
    dialogo.show()
    dialogo.set_proveedores([("Filtros del Valle", 3)])
    emitidos = _emitidos(dialogo)
    dialogo._al_guardar()
    assert emitidos == [] and dialogo._campos["proveedor_id"][1].isVisible()


# --- Pestaña de gastos ---------------------------------------------------------


def test_gasto_anulado_se_ve_tachado(qapp: QApplication) -> None:
    pestana = GastosWidget()
    pestana.mostrar_gastos(
        [
            FilaGasto(1, "09/10/2026", "Filtros", "Filtro", "1", "$ 45.000", "Sin soporte"),
            FilaGasto(
                2,
                "09/10/2026",
                "Filtros",
                "Duplicado",
                "1",
                "$ 45.000",
                "Sin soporte",
                anulado=True,
                motivo_anulacion="Duplicado",
            ),
        ]
    )
    assert not pestana._tabla.item(0, 2).font().strikeOut()
    assert pestana._tabla.item(1, 2).font().strikeOut()
    assert "Duplicado" in pestana._tabla.item(1, 2).toolTip()


# --- Recorrido completo por la ficha ------------------------------------------


@pytest.fixture
def ficha(qapp: QApplication) -> tuple[FichaPlantaController, PlantaService, GastoService]:
    almacen = AlmacenFake()
    fabrica = lambda: FakeUnidadDeTrabajo(almacen)  # noqa: E731
    plantas = PlantaService(fabrica, ConsecutivoService(), lambda: date(2026, 10, 9))
    gastos = GastoService(fabrica, lambda: date(2026, 10, 9))
    return FichaPlantaController(plantas, gastos, QWidget()), plantas, gastos


def test_registrar_y_anular_desde_la_ficha(ficha, monkeypatch: pytest.MonkeyPatch) -> None:
    controlador, plantas, gastos = ficha
    planta = plantas.registrar(
        DatosPlanta(
            marca="Perkins",
            potencia_kva=60,
            filtro_aceite="Perkins 2654407",
            tipo_aceite=TipoAceite.SAE_15W40,
            cantidad_aceite_gal=3.5,
        )
    )
    observado: dict = {}

    def usuario_registra(dialogo: RegistrarGastoDialog) -> int:
        dialogo.show()
        observado["sugerencias"] = [
            dialogo._descripcion.itemText(i) for i in range(dialogo._descripcion.count())
        ]
        dialogo._descripcion.setCurrentIndex(0)
        dialogo._sin_factura.setChecked(True)
        escribir_como_usuario(dialogo._valor, "45000")
        dialogo._al_guardar()
        return dialogo.result()

    def usuario_en_la_ficha(dialogo: FichaPlantaDialog) -> int:
        controlador.registrar_gasto()
        tabla = dialogo.gastos._tabla
        observado["filas"] = tabla.rowCount()
        observado["resumen"] = dialogo.gastos._resumen.text()
        tabla.selectRow(0)
        monkeypatch.setattr(dialogo.gastos, "pedir_motivo", lambda *_: "Valor mal digitado")
        dialogo.gastos._al_anular()
        observado["filas_tras_anular"] = tabla.rowCount()
        return 1

    monkeypatch.setattr(RegistrarGastoDialog, "exec", usuario_registra)
    monkeypatch.setattr(FichaPlantaDialog, "exec", usuario_en_la_ficha)

    controlador.abrir(planta.id, pestana="Gastos")

    assert observado["sugerencias"] == ["Filtro de aceite Perkins 2654407"]
    assert observado["filas"] == 1
    assert "$ 45.000" in observado["resumen"] and "Sin soporte" in observado["resumen"]
    assert observado["filas_tras_anular"] == 0  # Anulado: oculto por defecto
    assert gastos.resumen(planta.id).total == 0
