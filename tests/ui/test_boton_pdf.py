"""
Flujo completo del botón PDF del inventario (sin ventanas visibles).

Ruta: tests/ui/test_boton_pdf.py
"""

from datetime import date
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from src.business.models.estado_planta import EstadoPlanta
from src.business.models.hoja_vida import DatosEmpresa
from src.business.models.planta import DatosPlanta
from src.business.services.consecutivo_service import ConsecutivoService
from src.business.services.hoja_vida_service import HojaVidaService
from src.business.services.planta_service import PlantaService
from src.infrastructure.reports.pdf_hoja_vida import GeneradorPdfHojaVida
from src.presentation.controllers.inventario_controller import InventarioController
from src.presentation.views.equipos.inventario_view import InventarioView
from tests.unit.fakes import AlmacenFake, FakeUnidadDeTrabajo


class VistaSimulada(InventarioView):
    """Responde a los diálogos como lo haría un usuario, sin abrir ventanas."""

    def __init__(self, ruta_elegida: Path | None, eleccion: str = "cerrar") -> None:
        super().__init__()
        self.ruta_elegida = ruta_elegida
        self.eleccion = eleccion
        self.sugerida: Path | None = None
        self.abiertas: list[Path] = []
        self.mensajes: list[str] = []

    def pedir_ruta_guardado(self, titulo: str, sugerida: Path, filtro: str) -> Path | None:
        self.sugerida = sugerida
        return self.ruta_elegida

    def preguntar_tras_generar(self, titulo: str, mensaje: str) -> str:
        return self.eleccion

    def abrir_ruta(self, ruta: Path) -> bool:
        self.abiertas.append(ruta)
        return True

    def mostrar_error(self, titulo: str, mensaje: str) -> None:
        self.mensajes.append(mensaje)


def _preparar(qapp: QApplication, tmp_path: Path, vista: VistaSimulada):
    almacen = AlmacenFake()
    fabrica = lambda: FakeUnidadDeTrabajo(almacen)  # noqa: E731
    plantas = PlantaService(fabrica, ConsecutivoService(), lambda: date(2026, 10, 7))
    hojas = HojaVidaService(fabrica, GeneradorPdfHojaVida(), lambda: DatosEmpresa("WG"), "0.4.0")
    preferencias = QSettings(str(tmp_path / "preferencias.ini"), QSettings.Format.IniFormat)
    controlador = InventarioController(plantas, hojas, vista, preferencias=preferencias)
    planta = plantas.registrar(DatosPlanta(marca="Cummins", modelo="C50D6", potencia_kva=50))
    return plantas, controlador, planta, preferencias


def test_genera_el_pdf_recuerda_la_carpeta_y_lo_abre(qapp: QApplication, tmp_path: Path) -> None:
    destino = tmp_path / "salida" / "mi_hoja"  # Sin extensión: debe agregarse .pdf
    vista = VistaSimulada(destino, eleccion="abrir")
    _, controlador, planta, preferencias = _preparar(qapp, tmp_path, vista)

    controlador.generar_hoja_vida(planta.id)

    pdf = destino.with_name("mi_hoja.pdf")
    assert pdf.read_bytes().startswith(b"%PDF")
    assert vista.sugerida is not None and vista.sugerida.name.startswith("HV_PE-001_Cummins")
    assert preferencias.value("hojas_vida/carpeta") == str(pdf.parent)
    assert vista.abiertas == [pdf]


def test_cancelar_no_genera_nada(qapp: QApplication, tmp_path: Path) -> None:
    vista = VistaSimulada(ruta_elegida=None)
    _, controlador, planta, _ = _preparar(qapp, tmp_path, vista)
    controlador.generar_hoja_vida(planta.id)
    assert not list(tmp_path.rglob("*.pdf"))


def test_planta_vendida_sugiere_su_ultimo_numero(qapp: QApplication, tmp_path: Path) -> None:
    vista = VistaSimulada(ruta_elegida=None)
    plantas, controlador, planta, _ = _preparar(qapp, tmp_path, vista)
    plantas.cambiar_estado(planta.id, EstadoPlanta.VENDIDA, motivo="Venta")

    controlador.generar_hoja_vida(planta.id)

    assert vista.sugerida is not None and vista.sugerida.name.startswith("HV_PE-001_")


def test_error_al_guardar_se_informa_al_usuario(qapp: QApplication, tmp_path: Path) -> None:
    ocupado = tmp_path / "ocupado.pdf"
    ocupado.mkdir()  # Una carpeta con ese nombre impide escribir el archivo
    vista = VistaSimulada(ocupado)
    _, controlador, planta, _ = _preparar(qapp, tmp_path, vista)

    controlador.generar_hoja_vida(planta.id)

    assert any("No se pudo guardar" in m for m in vista.mensajes)


def test_la_tabla_tiene_el_boton_pdf(qapp: QApplication, tmp_path: Path) -> None:
    vista = VistaSimulada(None)
    _, controlador, _, _ = _preparar(qapp, tmp_path, vista)
    assert [clave for clave, _ in controlador._delegado._acciones][-1] == "pdf"
