"""
Componentes reutilizables del módulo comercial.

Ruta: src/presentation/widgets/comercial_widgets.py

- SelectorCliente: lista de clientes + botón "Nuevo cliente…".
- ContratoWidget: condiciones de un contrato (cliente, modalidad, tarifa).

Los usan el diálogo de cambio de estado (alquilar y vender) y el de
corrección de un contrato activo.
"""

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from src.presentation.widgets.campo_numerico import CampoNumerico

MODALIDADES: list[tuple[str, str]] = [("Por día", "DIA"), ("Por mes", "MES")]


class SelectorCliente(QWidget):
    """Lista de clientes con botón para crear uno nuevo sin salir del formulario."""

    nuevo_cliente_solicitado = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("envolturaCampo")
        self.combo = QComboBox()
        self.combo.setMinimumWidth(240)
        boton = QPushButton("Nuevo cliente…")
        boton.clicked.connect(self.nuevo_cliente_solicitado)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.combo, stretch=1)
        layout.addWidget(boton)
        self.set_clientes([])

    def set_clientes(self, clientes: list[tuple[str, int]], seleccionar: int | None = None) -> None:
        actual = self.combo.currentData() if seleccionar is None else seleccionar
        self.combo.clear()
        self.combo.addItem("Seleccione un cliente…", None)
        for nombre, cliente_id in clientes:
            self.combo.addItem(nombre, cliente_id)
        indice = self.combo.findData(actual) if actual is not None else 0
        self.combo.setCurrentIndex(max(indice, 0))

    def cliente_id(self) -> int | None:
        return self.combo.currentData()


class ContratoWidget(QWidget):
    """Condiciones de un contrato de alquiler."""

    nuevo_cliente_solicitado = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("envolturaCampo")
        self.cliente = SelectorCliente()
        self.cliente.nuevo_cliente_solicitado.connect(self.nuevo_cliente_solicitado)
        self._modalidad = QComboBox()
        for texto, clave in MODALIDADES:
            self._modalidad.addItem(texto, clave)
        self.tarifa = CampoNumerico(decimales=0, max_digitos=15, placeholder="Ej. 180.000")
        self._etiqueta_tarifa = QLabel()
        self._observaciones = QLineEdit()
        self._observaciones.setPlaceholderText("Ej. Obra en Jamundí, incluye transporte")

        formulario = QFormLayout(self)
        formulario.setContentsMargins(0, 0, 0, 0)
        formulario.addRow("Cliente *", self.cliente)
        formulario.addRow("Modalidad", self._modalidad)
        formulario.addRow(self._etiqueta_tarifa, self.tarifa)
        formulario.addRow("Observaciones", self._observaciones)
        self._modalidad.currentIndexChanged.connect(self._actualizar_etiqueta)
        self._actualizar_etiqueta()

    def set_clientes(self, clientes: list[tuple[str, int]], seleccionar: int | None = None) -> None:
        self.cliente.set_clientes(clientes, seleccionar)

    def cargar(
        self, cliente_id: int, modalidad: str, tarifa: int, observaciones: str | None
    ) -> None:
        self.cliente.set_clientes(
            [
                (self.cliente.combo.itemText(i), self.cliente.combo.itemData(i))
                for i in range(1, self.cliente.combo.count())
            ],
            cliente_id,
        )
        self._modalidad.setCurrentIndex(max(self._modalidad.findData(modalidad), 0))
        self.tarifa.set_valor(tarifa)
        self._observaciones.setText(observaciones or "")

    def valores(self) -> dict[str, Any]:
        return {
            "cliente_id": self.cliente.cliente_id(),
            "modalidad": self._modalidad.currentData(),
            "tarifa": self.tarifa.valor_entero() or 0,
            "observaciones": self._observaciones.text(),
        }

    def errores_de_formulario(self) -> dict[str, str]:
        """Revisiones propias de la interfaz antes de enviar."""
        errores: dict[str, str] = {}
        if self.cliente.cliente_id() is None:
            errores["cliente_id"] = "Seleccione el cliente o cree uno nuevo."
        if not self.tarifa.valor_entero():
            errores["tarifa"] = "Escriba la tarifa pactada."
        return errores

    def _actualizar_etiqueta(self) -> None:
        por_dia = self._modalidad.currentData() == "DIA"
        self._etiqueta_tarifa.setText("Tarifa diaria ($) *" if por_dia else "Tarifa mensual ($) *")
