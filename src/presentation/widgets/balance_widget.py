"""
Pestaña "Balance" de la ficha de una planta (Actividad 4.4).

Ruta: src/presentation/widgets/balance_widget.py

Arriba, el semáforo de reemplazo con sus razones; abajo, las cifras que lo
sustentan: lo que la planta deja (resultado de operación) y si ya pagó lo
que costó (recuperación de la inversión). El semáforo sugiere, no decide.
"""

from datetime import date
from typing import Final, NamedTuple

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.shared.colores import SEMAFORO

PERIODOS: Final[list[tuple[str, str]]] = [
    ("Todo el historial", "TODO"),
    ("Año actual", "ANIO"),
    ("Últimos 12 meses", "RECIENTE"),
    ("Rango de fechas…", "RANGO"),
]


class FilaBalance(NamedTuple):
    etiqueta: str
    valor: str
    detalle: str = ""
    negativo: bool = False  # Se pinta en rojo
    separador_antes: bool = False


class BalanceWidget(QWidget):
    periodo_cambiado = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._periodo = QComboBox()
        for texto, clave in PERIODOS:
            self._periodo.addItem(texto, clave)
        self._desde = self._selector_fecha(QDate(QDate.currentDate().year(), 1, 1))
        self._hasta = self._selector_fecha(QDate.currentDate())
        self._etiqueta_hasta = QLabel("al")

        barra = QHBoxLayout()
        barra.addWidget(QLabel("Período:"))
        barra.addWidget(self._periodo)
        barra.addWidget(self._desde)
        barra.addWidget(self._etiqueta_hasta)
        barra.addWidget(self._hasta)
        barra.addStretch()

        self._semaforo = QFrame()
        self._semaforo.setObjectName("semaforo")
        self._titulo_semaforo = QLabel()
        self._titulo_semaforo.setObjectName("tituloSemaforo")
        self._razones = QLabel()
        self._razones.setWordWrap(True)
        self._nota = QLabel(
            "El semáforo se calcula con toda la vida de la planta y los últimos "
            "meses, sin importar el período consultado. Sugiere, no decide."
        )
        self._nota.setObjectName("textoSecundario")
        self._nota.setWordWrap(True)
        layout_semaforo = QVBoxLayout(self._semaforo)
        layout_semaforo.addWidget(self._titulo_semaforo)
        layout_semaforo.addWidget(self._razones)

        self._cifras = QGridLayout()
        self._cifras.setColumnStretch(2, 1)
        self._cifras.setHorizontalSpacing(18)
        self._cifras.setVerticalSpacing(6)
        contenedor = QFrame()
        contenedor.setObjectName("panelNumeros")
        contenedor.setLayout(self._cifras)

        layout = QVBoxLayout(self)
        layout.addLayout(barra)
        layout.addWidget(self._semaforo)
        layout.addWidget(self._nota)
        layout.addWidget(contenedor)
        layout.addStretch()

        self._periodo.currentIndexChanged.connect(self._al_cambiar_periodo)
        self._desde.dateChanged.connect(lambda _f: self.periodo_cambiado.emit())
        self._hasta.dateChanged.connect(lambda _f: self.periodo_cambiado.emit())
        self._mostrar_rango(False)

    @staticmethod
    def _selector_fecha(inicial: QDate) -> QDateEdit:
        selector = QDateEdit(inicial)
        selector.setCalendarPopup(True)
        selector.setDisplayFormat("dd/MM/yyyy")
        return selector

    # --- API pública ------------------------------------------------------

    def periodo_elegido(self) -> tuple[str, date, date]:
        """(clave del período, desde, hasta). Las fechas solo aplican al rango."""
        return (
            self._periodo.currentData(),
            self._desde.date().toPython(),
            self._hasta.date().toPython(),
        )

    def mostrar_semaforo(self, nivel: str, titulo: str, razones: list[str]) -> None:
        fondo, color = SEMAFORO.get(nivel, SEMAFORO["SIN_DATOS"])
        self._semaforo.setStyleSheet(
            f"#semaforo {{ background-color: {fondo}; border-left: 6px solid {color};"
            f" border-radius: 6px; }}"
        )
        self._titulo_semaforo.setText(titulo)
        self._titulo_semaforo.setStyleSheet(
            f"color: {color}; font-size: 13pt; font-weight: bold; background: transparent;"
        )
        self._razones.setText("<br>".join(f"• {r}" for r in razones) if razones else "")
        self._razones.setVisible(bool(razones))

    def mostrar_cifras(self, filas: list[FilaBalance]) -> None:
        while self._cifras.count():  # Limpia la cuadrícula anterior
            elemento = self._cifras.takeAt(0)
            if elemento.widget() is not None:
                elemento.widget().deleteLater()
        fila_grilla = 0
        for fila in filas:
            if fila.separador_antes:
                linea = QFrame()
                linea.setFrameShape(QFrame.Shape.HLine)
                linea.setStyleSheet("color: #D5DCE3;")
                self._cifras.addWidget(linea, fila_grilla, 0, 1, 3)
                fila_grilla += 1
            etiqueta = QLabel(fila.etiqueta)
            etiqueta.setObjectName("datoSistema")
            valor = QLabel(fila.valor)
            valor.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            color = "#C0392B" if fila.negativo else "#1F2933"
            valor.setStyleSheet(f"color: {color}; font-weight: bold; background: transparent;")
            detalle = QLabel(fila.detalle)
            detalle.setObjectName("textoSecundario")
            detalle.setWordWrap(True)
            self._cifras.addWidget(etiqueta, fila_grilla, 0)
            self._cifras.addWidget(valor, fila_grilla, 1)
            self._cifras.addWidget(detalle, fila_grilla, 2)
            fila_grilla += 1

    def _al_cambiar_periodo(self) -> None:
        self._mostrar_rango(self._periodo.currentData() == "RANGO")
        self.periodo_cambiado.emit()

    def _mostrar_rango(self, visible: bool) -> None:
        for control in (self._desde, self._etiqueta_hasta, self._hasta):
            control.setVisible(visible)
