"""
Pruebas de interfaz del módulo de mantenimientos.

Ruta: tests/ui/test_mantenimientos_ui.py
"""

from datetime import date, datetime

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from src.business.models.estado_planta import EstadoPlanta as E
from src.business.models.mantenimiento import (
    AlertaMantenimiento,
    DatosMantenimiento,
    NivelAlerta,
    TipoMantenimiento,
)
from src.business.models.planta import DatosPlanta, Planta, TipoAceite
from src.business.services.consecutivo_service import ConsecutivoService
from src.business.services.gasto_service import GastoService
from src.business.services.mantenimiento_service import MantenimientoService
from src.business.services.planta_service import PlantaService
from src.presentation.controllers.ficha_controller import FichaPlantaController
from src.presentation.controllers.inventario_controller import _texto_alerta
from src.presentation.dialogs.ficha_planta_dialog import FichaPlantaDialog
from src.presentation.dialogs.mantenimiento_dialog import RegistrarMantenimientoDialog
from tests.ui.conftest import escribir_como_usuario
from tests.unit.fakes import AlmacenFake, FakeUnidadDeTrabajo

HOY = date(2026, 10, 9)
INSUMOS_FICHA = [(1, "Filtro de aceite LF3000", 1.0, "Unidad"), (3, "Aceite 15W-40", 3.5, "Galón")]


def _dialogo(insumos_ficha=INSUMOS_FICHA) -> RegistrarMantenimientoDialog:
    dialogo = RegistrarMantenimientoDialog(
        "PE-004 · Perkins P110",
        "2.075 h",
        [("Preventivo", "PREVENTIVO"), ("Correctivo", "CORRECTIVO")],
        ["Juan Pérez"],
        [("Filtros", 1), ("Aceite y lubricantes", 3), ("Mano de obra", 4)],
        insumos_ficha,
        ["Unidad", "Galón", "Servicio"],
        sugeridor=lambda fecha, horas: MantenimientoService.proximo_sugerido(fecha, horas, 6, 250),
    )
    dialogo.show()
    return dialogo


def test_horometro_es_obligatorio(qapp: QApplication) -> None:
    dialogo = _dialogo()
    emitidos: list = []
    dialogo.guardar_solicitado.connect(emitidos.append)
    dialogo._al_guardar()
    assert emitidos == [] and dialogo._campos["horometro"][1].isVisible()


def test_preventivo_sugiere_el_proximo_al_escribir_el_horometro(qapp: QApplication) -> None:
    dialogo = _dialogo()
    escribir_como_usuario(dialogo._horometro, "2100")
    dialogo._horometro.editingFinished.emit()

    valores = dialogo.valores()
    assert valores["proximo_horometro"] == 2350
    assert valores["proxima_fecha"] is not None


def test_correctivo_no_sugiere_nada(qapp: QApplication) -> None:
    dialogo = _dialogo()
    dialogo._tipo.setCurrentIndex(dialogo._tipo.findData("CORRECTIVO"))
    escribir_como_usuario(dialogo._horometro, "2100")
    dialogo._horometro.editingFinished.emit()
    assert dialogo.valores()["proximo_horometro"] is None


def test_cargar_insumos_de_la_ficha_y_escribir_valores(qapp: QApplication) -> None:
    dialogo = _dialogo()
    dialogo.cargar_insumos_ficha()
    dialogo.escribir_celda(0, 4, "45.000")
    dialogo.escribir_celda(1, 4, "130000")
    dialogo.escribir_celda(1, 2, "3,5")

    insumos = dialogo.valores()["insumos"]
    assert [(i["descripcion"], i["cantidad"], i["valor_total"]) for i in insumos] == [
        ("Filtro de aceite LF3000", 1.0, 45_000),
        ("Aceite 15W-40", 3.5, 130_000),
    ]
    assert "175.000" in dialogo._total.text()


def test_sin_datos_en_la_ficha_el_boton_de_carga_se_deshabilita(qapp: QApplication) -> None:
    dialogo = _dialogo(insumos_ficha=[])
    botones = [b for b in dialogo.findChildren(type(dialogo._soporte._boton_nueva))]
    cargar = next(b for b in botones if b.text().startswith("Cargar insumos"))
    assert not cargar.isEnabled()


def test_sin_insumos_no_se_envia_factura(qapp: QApplication) -> None:
    dialogo = _dialogo()
    assert dialogo.valores()["factura_id"] is None


@pytest.mark.parametrize(
    ("nivel", "dias", "horas", "esperado"),
    [
        (NivelAlerta.VENCIDO, -3, None, "PE-004 · Vencido: hace 3 día(s)"),
        (NivelAlerta.VENCIDO, None, -10, "PE-004 · Vencido: 10 h pasado"),
        (NivelAlerta.PROXIMO, 12, 20, "PE-004 · Próximo: en 12 día(s) / en 20 h"),
    ],
)
def test_texto_de_las_alertas(nivel, dias, horas, esperado) -> None:
    planta = Planta(
        1, 4, E.DISPONIBLE, DatosPlanta(marca="Perkins", potencia_kva=60), datetime(2026, 1, 1), 0
    )
    alerta = AlertaMantenimiento(planta, nivel, None, None, dias, horas)
    assert _texto_alerta(alerta) == esperado


def test_registrar_mantenimiento_desde_la_ficha(qapp: QApplication, monkeypatch) -> None:
    # Los formularios usan el reloj real (QDate.currentDate), así que en este recorrido
    # los servicios también: con un reloj fijo, la prueba "caducaría" con los días.
    almacen = AlmacenFake()
    fabrica = lambda: FakeUnidadDeTrabajo(almacen)  # noqa: E731
    plantas = PlantaService(fabrica, ConsecutivoService())
    gastos = GastoService(fabrica)
    mantenimientos = MantenimientoService(fabrica)
    hoy = date.today()
    planta = plantas.registrar(
        DatosPlanta(
            marca="Perkins",
            potencia_kva=60,
            horometro_inicial=2000,
            filtro_aceite="LF3000",
            tipo_aceite=TipoAceite.SAE_15W40,
        )
    )
    controlador = FichaPlantaController(plantas, gastos, mantenimientos, QWidget())
    observado: dict = {}

    def usuario_registra(dialogo: RegistrarMantenimientoDialog) -> int:
        dialogo.show()
        escribir_como_usuario(dialogo._horometro, "2100")
        dialogo._horometro.editingFinished.emit()
        dialogo._descripcion.setPlainText("Cambio de aceite y filtros")
        dialogo.cargar_insumos_ficha()
        dialogo.escribir_celda(0, 4, "45000")
        dialogo.escribir_celda(1, 4, "130000")
        dialogo._soporte.usar_sin_factura()
        dialogo._al_guardar()
        return dialogo.result()

    def usuario_en_la_ficha(ficha: FichaPlantaDialog) -> int:
        controlador.registrar_mantenimiento()
        observado["mantenimientos"] = ficha.mantenimientos._tabla.rowCount()
        observado["resumen"] = ficha.mantenimientos._resumen.text()
        observado["gastos"] = ficha.gastos._tabla.rowCount()
        observado["descripcion_gasto"] = ficha.gastos._tabla.item(0, 2).text()
        return 1

    monkeypatch.setattr(RegistrarMantenimientoDialog, "exec", usuario_registra)
    monkeypatch.setattr(FichaPlantaDialog, "exec", usuario_en_la_ficha)
    controlador.abrir(planta.id, "Mantenimientos")

    assert observado["mantenimientos"] == 1
    assert "2.100 h" in observado["resumen"] and "2.350 h" in observado["resumen"]
    assert observado["gastos"] == 2  # Los insumos aparecen también en Gastos
    assert f"(mantenimiento {hoy:%d/%m/%Y})" in observado["descripcion_gasto"]
    assert plantas.obtener(planta.id).horometro_actual == 2100
    proxima_fecha, proximas_horas = MantenimientoService.proximo_sugerido(hoy, 2100, 6, 250)
    assert mantenimientos.ultimo(planta.id).datos == DatosMantenimiento(
        hoy,
        TipoMantenimiento.PREVENTIVO,
        2100,
        "Cambio de aceite y filtros",
        None,
        proxima_fecha,
        proximas_horas,
    )
