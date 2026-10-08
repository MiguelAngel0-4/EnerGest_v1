"""
Pruebas de interfaz del módulo comercial (Actividad 4.3).

Ruta: tests/ui/test_ingresos_ui.py

Los recorridos usan el reloj real, igual que los formularios (ver la lección
de la "bomba de tiempo" del ciclo 6).
"""

from datetime import date, datetime

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from src.business.models.comercial import DatosContrato, ModalidadAlquiler, TipoIngreso
from src.business.models.estado_planta import EstadoPlanta as E
from src.business.models.hoja_vida import DatosEmpresa
from src.business.models.planta import DatosPlanta, Planta
from src.business.services.comercial_service import ComercialService
from src.business.services.consecutivo_service import ConsecutivoService
from src.business.services.gasto_service import GastoService
from src.business.services.hoja_vida_service import HojaVidaService
from src.business.services.mantenimiento_service import MantenimientoService
from src.business.services.planta_service import PlantaService
from src.infrastructure.reports.pdf_hoja_vida import GeneradorPdfHojaVida
from src.presentation.controllers.ficha_controller import FichaPlantaController
from src.presentation.controllers.inventario_controller import InventarioController
from src.presentation.dialogs.cambiar_estado_dialog import (
    CambiarEstadoDialog,
    OpcionEstado,
    VistaLiquidacion,
)
from src.presentation.dialogs.comercial_dialogs import RegistrarIngresoDialog
from src.presentation.dialogs.ficha_planta_dialog import FichaPlantaDialog
from src.presentation.table_models.plantas_table_model import Columna, PlantasTableModel
from src.presentation.views.equipos.inventario_view import InventarioView
from tests.ui.conftest import escribir_como_usuario
from tests.unit.fakes import AlmacenFake, FakeUnidadDeTrabajo

OPCIONES = [
    OpcionEstado("ALQUILADA", "Alquilada", False, "", True, True, "contrato"),
    OpcionEstado("VENDIDA", "Vendida", False, "", seccion="venta"),
    OpcionEstado("EN_MANTENIMIENTO", "En mantenimiento", False, ""),
]
CLIENTES = [("Constructora del Pacífico", 7)]


def _dialogo(liquidador=None) -> CambiarEstadoDialog:
    dialogo = CambiarEstadoDialog(
        "PE-004 · Perkins",
        "Disponible",
        OPCIONES,
        date(2026, 1, 1),
        "1.000 h",
        liquidador=liquidador,
    )
    dialogo.set_clientes(CLIENTES)
    dialogo.show()
    return dialogo


def _elegir(dialogo: CambiarEstadoDialog, clave: str) -> None:
    dialogo._combo.setCurrentIndex(dialogo._combo.findData(clave))
    QApplication.processEvents()


# --- Secciones del diálogo de estado -------------------------------------------


def test_cada_destino_muestra_solo_su_seccion(qapp: QApplication) -> None:
    dialogo = _dialogo()
    _elegir(dialogo, "ALQUILADA")
    assert dialogo._grupo_contrato.isVisible() and not dialogo._grupo_venta.isVisible()
    _elegir(dialogo, "VENDIDA")
    assert dialogo._grupo_venta.isVisible() and not dialogo._grupo_contrato.isVisible()
    _elegir(dialogo, "EN_MANTENIMIENTO")
    assert not dialogo._grupo_venta.isVisible() and not dialogo._grupo_contrato.isVisible()
    assert not dialogo._grupo_liquidacion.isVisible()  # Sin contrato activo


def test_alquilar_sin_cliente_ni_tarifa_no_se_envia(qapp: QApplication) -> None:
    dialogo = _dialogo()
    emitidos: list = []
    dialogo.cambio_solicitado.connect(lambda *a: emitidos.append(a))
    _elegir(dialogo, "ALQUILADA")
    escribir_como_usuario(dialogo._horometro, "1020")
    dialogo._al_actualizar()
    assert emitidos == [] and dialogo._error.isVisible()


def test_datos_del_contrato_se_leen_del_formulario(qapp: QApplication) -> None:
    dialogo = _dialogo()
    _elegir(dialogo, "ALQUILADA")
    contrato = dialogo._contrato
    contrato.cliente.combo.setCurrentIndex(contrato.cliente.combo.findData(7))
    contrato._modalidad.setCurrentIndex(contrato._modalidad.findData("MES"))
    escribir_como_usuario(contrato.tarifa, "3000000")
    assert dialogo.datos_comerciales()["contrato"] == {
        "cliente_id": 7,
        "modalidad": "MES",
        "tarifa": 3_000_000,
        "observaciones": "",
    }
    assert "mensual" in contrato._etiqueta_tarifa.text()


def test_liquidacion_se_recalcula_con_la_fecha_sin_pisar_lo_editado(qapp: QApplication) -> None:
    llamadas: list[date] = []

    def liquidador(fecha: date) -> VistaLiquidacion:
        llamadas.append(fecha)
        return VistaLiquidacion("detalle", 100_000 * (len(llamadas)), 50_000)

    dialogo = _dialogo(liquidador)
    _elegir(dialogo, "EN_MANTENIMIENTO")
    assert dialogo._grupo_liquidacion.isVisible()
    assert "Saldo: $ " in dialogo._saldo.text()

    escribir_como_usuario(dialogo._valor_liquidado, "9")  # El usuario negocia otro valor
    dialogo._fecha.setDate(dialogo._fecha.date().addDays(-1))
    valor = dialogo.datos_comerciales()["liquidacion"]["valor_liquidado"]
    assert str(valor).endswith("9")  # No se reemplazó por el recálculo


def test_tooltip_del_cliente_en_el_inventario(qapp: QApplication) -> None:
    modelo = PlantasTableModel()
    planta = Planta(
        4, 4, E.ALQUILADA, DatosPlanta(marca="Perkins", potencia_kva=60), datetime(2026, 1, 1), 0
    )
    modelo.cargar([planta])
    modelo.set_clientes_actuales({4: "Eventos del Valle"})
    indice = modelo.index(0, Columna.ESTADO)
    assert modelo.data(indice, 3) == "Alquilada a Eventos del Valle"  # 3 = ToolTipRole


# --- Recorridos completos ----------------------------------------------------------


class Entorno:
    def __init__(self) -> None:
        almacen = AlmacenFake()
        fabrica = lambda: FakeUnidadDeTrabajo(almacen)  # noqa: E731
        self.plantas = PlantaService(fabrica, ConsecutivoService())
        self.comercial = ComercialService(fabrica, self.plantas)
        self.gastos = GastoService(fabrica)
        self.mantenimientos = MantenimientoService(fabrica)
        self.hojas = HojaVidaService(
            fabrica, GeneradorPdfHojaVida(), lambda: DatosEmpresa("WG"), "0.7"
        )
        self.cliente = self.comercial.registrar_cliente("Constructora del Pacífico")
        datos = DatosPlanta(marca="Perkins", potencia_kva=60, horometro_inicial=1000)
        self.planta = self.plantas.registrar(datos).id


@pytest.fixture
def e(qapp: QApplication) -> Entorno:
    return Entorno()


def test_alquilar_y_devolver_desde_el_inventario(e: Entorno, monkeypatch) -> None:
    vista = InventarioView()
    monkeypatch.setattr(vista, "mostrar_info", lambda *a: None)
    control = InventarioController(e.plantas, e.hojas, vista, comercial=e.comercial)

    def usuario_alquila(dialogo: CambiarEstadoDialog) -> int:
        dialogo.show()
        _elegir(dialogo, "ALQUILADA")
        combo = dialogo._contrato.cliente.combo
        combo.setCurrentIndex(combo.findData(e.cliente.id))
        escribir_como_usuario(dialogo._contrato.tarifa, "180000")
        escribir_como_usuario(dialogo._horometro, "1020")
        dialogo._al_actualizar()
        return dialogo.result()

    monkeypatch.setattr(CambiarEstadoDialog, "exec", usuario_alquila)
    control.cambiar_estado(e.planta)
    activo = e.comercial.contrato_activo(e.planta)
    assert activo is not None and activo.tarifa == 180_000
    assert control._modelo._clientes == {e.planta: "Constructora del Pacífico"}

    def usuario_devuelve(dialogo: CambiarEstadoDialog) -> int:
        dialogo.show()
        _elegir(dialogo, "DISPONIBLE")
        assert dialogo._grupo_liquidacion.isVisible()
        escribir_como_usuario(dialogo._horometro, "1100")
        dialogo._al_actualizar()
        return dialogo.result()

    monkeypatch.setattr(CambiarEstadoDialog, "exec", usuario_devuelve)
    control.cambiar_estado(e.planta)

    cerrado = e.comercial.alquileres(e.planta)[0]
    assert not cerrado.activo and cerrado.valor_liquidado == 180_000  # Mínimo un día
    assert cerrado.saldo == 0 and cerrado.horas_uso == 80
    assert e.comercial.ingresos(e.planta)[0].tipo is TipoIngreso.ALQUILER


def test_cobrar_y_anular_desde_la_ficha(e: Entorno, monkeypatch) -> None:
    e.comercial.alquilar(
        e.planta, DatosContrato(e.cliente.id, ModalidadAlquiler.DIA, 100_000), horometro=1020
    )
    ficha = FichaPlantaController(
        e.plantas, e.gastos, e.mantenimientos, QWidget(), comercial=e.comercial
    )
    observado: dict = {}

    def usuario_cobra(dialogo: RegistrarIngresoDialog) -> int:
        dialogo.show()
        assert dialogo._concepto.currentText().startswith("Contrato activo")
        escribir_como_usuario(dialogo._valor, "100000")
        dialogo._al_guardar()
        return dialogo.result()

    def usuario_en_la_ficha(dialogo: FichaPlantaDialog) -> int:
        observado["contrato"] = dialogo.ingresos._contrato.text()
        ficha.registrar_ingreso()
        observado["filas"] = dialogo.ingresos._tabla.rowCount()
        observado["resumen"] = dialogo.ingresos._resumen.text()
        dialogo.ingresos._tabla.selectRow(0)
        monkeypatch.setattr(dialogo.ingresos, "pedir_motivo", lambda *a: "Consignación rechazada")
        dialogo.ingresos._al_anular()
        observado["tras_anular"] = dialogo.ingresos._tabla.rowCount()
        return 1

    monkeypatch.setattr(RegistrarIngresoDialog, "exec", usuario_cobra)
    monkeypatch.setattr(FichaPlantaDialog, "exec", usuario_en_la_ficha)
    ficha.abrir(e.planta, "Ingresos")

    assert "Contrato activo" in observado["contrato"]
    assert observado["filas"] == 1 and "$ 100.000" in observado["resumen"]
    assert observado["tras_anular"] == 0
    assert e.comercial.contrato_activo(e.planta).cobrado == 0
