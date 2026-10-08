"""
Selector de soporte de un gasto: con factura (y cuál) o sin factura.

Ruta: src/presentation/widgets/selector_factura.py

Lo usan el formulario de gasto y el de mantenimiento. Muestra el saldo por
asignar de la factura elegida y permite crear una nueva sin salir del formulario.
"""

from typing import NamedTuple

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class OpcionFactura(NamedTuple):
    """Factura con saldo, tal como se ofrece en la lista."""

    id: int
    texto: str  # Ej. "FE-0042 · Filtros del Valle"
    saldo: str  # Ej. "$ 120.000"


class SelectorFactura(QWidget):
    """Opción con/sin factura + lista de facturas con saldo + botón "Nueva factura…"."""

    nueva_factura_solicitada = Signal()

    def __init__(self, parent: QWidget | None = None, compacto: bool = False) -> None:
        """
        Args:
            compacto: Opciones y lista en una sola fila (para formularios anchos).
        """
        super().__init__(parent)
        self.setObjectName("envolturaCampo")
        self._saldos: dict[int, str] = {}

        self._con_factura = QRadioButton("Con factura")
        self._sin_factura = QRadioButton("Sin factura (compra informal)")
        self._con_factura.setChecked(True)  # Lo habitual en la empresa
        for opcion in (self._con_factura, self._sin_factura):
            # El texto de las opciones nunca se recorta: la lista cede el espacio.
            opcion.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        grupo = QButtonGroup(self)
        grupo.addButton(self._con_factura)
        grupo.addButton(self._sin_factura)

        self.combo = QComboBox()
        self.combo.setMinimumWidth(300)
        self._boton_nueva = QPushButton("Nueva factura…")
        self._saldo = QLabel()
        self._saldo.setObjectName("textoSecundario")

        opciones = QHBoxLayout()
        opciones.addWidget(self._con_factura)
        opciones.addWidget(self._sin_factura)
        fila = QHBoxLayout()
        fila.addWidget(self.combo, stretch=1)
        fila.addWidget(self._boton_nueva)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        if compacto:
            opciones.addLayout(fila, stretch=1)
            layout.addLayout(opciones)
        else:
            opciones.addStretch()
            layout.addLayout(opciones)
            layout.addLayout(fila)
        layout.addWidget(self._saldo)

        self.combo.currentIndexChanged.connect(self._actualizar_saldo)
        self._con_factura.toggled.connect(self._al_cambiar_opcion)
        self._boton_nueva.clicked.connect(self.nueva_factura_solicitada)
        self.set_facturas([])

    def set_facturas(self, facturas: list[OpcionFactura], seleccionar: int | None = None) -> None:
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItem("Seleccione una factura…", None)
        self._saldos = {}
        for opcion in facturas:
            # El saldo va debajo de la lista, no en ella: así el texto no se corta.
            self.combo.addItem(opcion.texto, opcion.id)
            self._saldos[opcion.id] = opcion.saldo
        indice = self.combo.findData(seleccionar) if seleccionar is not None else 0
        self.combo.setCurrentIndex(max(indice, 0))
        self.combo.blockSignals(False)
        self._actualizar_saldo()

    def usar_sin_factura(self) -> None:
        self._sin_factura.setChecked(True)

    def factura_id(self) -> int | None:
        """Factura elegida, o None si se marcó "Sin factura"."""
        return self.combo.currentData() if self._con_factura.isChecked() else None

    def falta_seleccion(self) -> bool:
        """True si marcó "Con factura" pero no eligió ninguna."""
        return self._con_factura.isChecked() and self.combo.currentData() is None

    def texto_saldo(self) -> str:
        return self._saldo.text()

    def _actualizar_saldo(self) -> None:
        factura_id = self.combo.currentData()
        self._saldo.setText(
            f"Saldo por asignar: {self._saldos[factura_id]}" if factura_id in self._saldos else ""
        )

    def _al_cambiar_opcion(self, con_factura: bool) -> None:
        self.combo.setEnabled(con_factura)
        self._boton_nueva.setEnabled(con_factura)
        self._saldo.setVisible(con_factura)
