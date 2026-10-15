"""
Selector de período compartido por la pestaña Balance y los Reportes financieros.

Ruta: src/presentation/widgets/selector_periodo.py
"""

from datetime import date
from typing import Final

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import QComboBox, QDateEdit, QHBoxLayout, QLabel, QWidget

PERIODOS: Final[list[tuple[str, str]]] = [
    ("Todo el historial", "TODO"),
    ("Año actual", "ANIO"),
    ("Últimos 12 meses", "RECIENTE"),
    ("Rango de fechas…", "RANGO"),
]


class SelectorPeriodo(QWidget):
    """Lista de períodos; con "Rango de fechas…" aparecen los selectores de fecha."""

    periodo_cambiado = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.combo = QComboBox()
        for texto, clave in PERIODOS:
            self.combo.addItem(texto, clave)
        self.desde = self._selector_fecha(QDate(QDate.currentDate().year(), 1, 1))
        self.hasta = self._selector_fecha(QDate.currentDate())
        self._al = QLabel("al")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Período:"))
        layout.addWidget(self.combo)
        layout.addWidget(self.desde)
        layout.addWidget(self._al)
        layout.addWidget(self.hasta)

        self.combo.currentIndexChanged.connect(self._al_cambiar)
        self.desde.dateChanged.connect(lambda _f: self.periodo_cambiado.emit())
        self.hasta.dateChanged.connect(lambda _f: self.periodo_cambiado.emit())
        self._mostrar_rango(False)

    def elegido(self) -> tuple[str, date, date]:
        """(clave del período, desde, hasta). Las fechas solo aplican al rango."""
        return self.combo.currentData(), self.desde.date().toPython(), self.hasta.date().toPython()

    @staticmethod
    def _selector_fecha(inicial: QDate) -> QDateEdit:
        selector = QDateEdit(inicial)
        selector.setCalendarPopup(True)
        selector.setDisplayFormat("dd/MM/yyyy")
        return selector

    def _al_cambiar(self) -> None:
        self._mostrar_rango(self.combo.currentData() == "RANGO")
        self.periodo_cambiado.emit()

    def _mostrar_rango(self, visible: bool) -> None:
        for control in (self.desde, self._al, self.hasta):
            control.setVisible(visible)
