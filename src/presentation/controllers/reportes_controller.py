"""
Controlador de la pantalla Reportes financieros (Actividad 4.4).

Ruta: src/presentation/controllers/reportes_controller.py
"""

import logging
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Final

from PySide6.QtCore import QObject, QSettings, QStandardPaths, QUrl
from PySide6.QtGui import QDesktopServices

from src.business.exceptions import DocumentoError, NegocioError
from src.business.models.rentabilidad import FilaReporte, Periodo, ResumenFinanciero
from src.business.services.rentabilidad_service import IExportadorReporte, RentabilidadService
from src.presentation.controllers.periodos import periodo_desde_seleccion
from src.presentation.table_models.reporte_table_model import FilaTablaReporte
from src.presentation.views.reportes.reportes_view import ReportesView, Tarjeta
from src.shared.formatters import formatear_consecutivo, formatear_moneda

logger = logging.getLogger(__name__)

_CLAVE_CARPETA: Final[str] = "reportes/carpeta"
_MESES: Final[list[str]] = [
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "sep",
    "oct",
    "nov",
    "dic",
]


class ReportesController(QObject):
    def __init__(
        self,
        rentabilidad: RentabilidadService,
        exportador: IExportadorReporte,
        vista: ReportesView,
        abrir_ficha: Callable[[int, str], None] | None = None,
        parent: QObject | None = None,
        preferencias: QSettings | None = None,
    ) -> None:
        """
        Args:
            abrir_ficha: Abre la ficha de una planta en una pestaña (la del inventario).
        """
        super().__init__(parent)
        self._rentabilidad = rentabilidad
        self._exportador = exportador
        self._vista = vista
        self._abrir_ficha = abrir_ficha
        self._preferencias = preferencias or QSettings("EnerGest", "EnerGest")

        vista.mostrada.connect(self.recargar)
        vista.periodo_cambiado.connect(self.recargar)
        vista.incluir_cambiado.connect(self.recargar)
        vista.exportar_solicitado.connect(self.exportar)
        vista.planta_seleccionada.connect(self._ver_planta)

    def periodo(self) -> Periodo:
        clave, desde, hasta = self._vista.periodo.elegido()
        return periodo_desde_seleccion(clave, desde, hasta, self._rentabilidad)

    def recargar(self) -> None:
        try:
            resumen = self._rentabilidad.resumen(
                self.periodo(), self._vista.incluir_fuera_de_operacion()
            )
        except NegocioError as exc:
            self._vista.mostrar_error("Reportes financieros", str(exc))
            return
        except Exception:
            logger.exception("Error inesperado al cargar los reportes.")
            self._vista.mostrar_error(
                "Reportes financieros", "Ocurrió un error inesperado. Los detalles están en el log."
            )
            return
        self._vista.mostrar_tarjetas(_tarjetas(resumen))
        self._vista.mostrar_meses(
            [_mes(m.mes) for m in resumen.meses],
            [m.ingresos for m in resumen.meses],
            [m.gastos for m in resumen.meses],
        )
        self._vista.mostrar_filas([_fila(f) for f in resumen.filas])
        evaluar = sum(1 for f in resumen.filas if f.indicador.nivel.value == "EVALUAR_REEMPLAZO")
        vigilar = sum(1 for f in resumen.filas if f.indicador.nivel.value == "VIGILAR")
        self._vista.mostrar_pie(
            f"{len(resumen.filas)} planta(s) · {evaluar} para evaluar reemplazo · "
            f"{vigilar} para vigilar · Doble clic en una fila para abrir su balance."
        )

    def exportar(self) -> None:
        carpeta = Path(
            str(
                self._preferencias.value(
                    _CLAVE_CARPETA,
                    QStandardPaths.writableLocation(
                        QStandardPaths.StandardLocation.DocumentsLocation
                    ),
                )
            )
        )
        sugerida = carpeta / f"Reporte_financiero_{date.today():%Y-%m-%d}.xlsx"
        ruta = self._vista.pedir_ruta_guardado(str(sugerida))
        if ruta is None:
            return
        destino = Path(ruta)
        try:
            with self._vista.cursor_espera():
                self._rentabilidad.exportar(
                    self.periodo(),
                    self._exportador,
                    destino,
                    self._vista.incluir_fuera_de_operacion(),
                )
        except DocumentoError as exc:
            self._vista.mostrar_error("Exportar a Excel", str(exc))
            return
        except Exception:
            logger.exception("Error inesperado al exportar el reporte.")
            self._vista.mostrar_error(
                "Exportar a Excel", "Ocurrió un error inesperado. Los detalles están en el log."
            )
            return
        self._preferencias.setValue(_CLAVE_CARPETA, str(destino.parent))
        if self._vista.preguntar_abrir(str(destino)):
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(destino)))

    def _ver_planta(self, planta_id: int) -> None:
        if self._abrir_ficha is None:
            return
        self._abrir_ficha(planta_id, "Balance")
        self.recargar()  # Lo registrado en la ficha se refleja al volver


def _mes(clave: str) -> str:
    """'2026-10' -> 'oct 2026'."""
    anio, mes = clave.split("-")
    return f"{_MESES[int(mes) - 1]} {anio}"


def _tarjetas(resumen: ResumenFinanciero) -> list[Tarjeta]:
    return [
        Tarjeta("Ingresos", formatear_moneda(resumen.ingresos), "Alquileres, ventas y otros"),
        Tarjeta("Gastos", formatear_moneda(resumen.gastos), "Incluye insumos de mantenimiento"),
        Tarjeta(
            "Resultado",
            formatear_moneda(resumen.resultado),
            "Ingresos menos gastos",
            negativo=resumen.resultado < 0,
        ),
        Tarjeta(
            "Saldo por cobrar",
            formatear_moneda(resumen.saldo_por_cobrar),
            "De alquileres ya cerrados",
        ),
    ]


def _fila(fila: FilaReporte) -> FilaTablaReporte:
    planta, totales, indicador = fila.planta, fila.totales, fila.indicador
    numero = planta.numero_consecutivo
    return FilaTablaReporte(
        planta_id=planta.id,
        numero=formatear_consecutivo(numero),
        numero_orden=numero if numero is not None else 10**6,
        planta=" ".join(filter(None, [planta.datos.marca, planta.datos.modelo])),
        estado=planta.estado.etiqueta,
        ingresos=totales.ingresos_operacion + totales.ingresos_venta,
        gastos=totales.gastos,
        resultado=totales.ingresos_operacion + totales.ingresos_venta - totales.gastos,
        desgaste=indicador.desgaste_pct,
        nivel=indicador.nivel.value,
        nivel_texto=indicador.nivel.etiqueta,
        razones=" ".join(indicador.razones),
    )
