"""
Pestaña "Balance" de la ficha de una planta (Actividad 4.4).

Ruta: src/presentation/widgets/balance_widget.py

Arriba, el semáforo de reemplazo con sus razones; abajo, las cifras que lo
sustentan: lo que la planta deja (resultado de operación) y si ya pagó lo
que costó (recuperación de la inversión). El semáforo sugiere, no decide.
"""

from datetime import date
from typing import NamedTuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.presentation.widgets.selector_periodo import SelectorPeriodo
from src.shared.colores import SEMAFORO


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
        self._selector = SelectorPeriodo()
        # Nombres internos conservados (los usan las pruebas de la R2).
        self._periodo = self._selector.combo
        self._desde = self._selector.desde
        self._hasta = self._selector.hasta
        barra = QHBoxLayout()
        barra.addWidget(self._selector)
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

        self._selector.periodo_cambiado.connect(self.periodo_cambiado)

    # --- API pública ------------------------------------------------------

    def periodo_elegido(self) -> tuple[str, date, date]:
        """(clave del período, desde, hasta). Las fechas solo aplican al rango."""
        return self._selector.elegido()

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
