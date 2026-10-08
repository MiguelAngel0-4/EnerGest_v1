"""
Pestaña "Ingresos" de la ficha de una planta (Actividad 4.3).

Ruta: src/presentation/widgets/ingresos_widget.py

Tres partes, de arriba abajo:
1. El contrato activo (si lo hay), con el botón para corregir sus condiciones.
2. La lista de ingresos (base común RegistrosWidget: registrar, anular, ver anulados).
3. El historial de alquileres, con horas de uso, liquidado, cobrado y saldo.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.presentation.widgets.registros_widget import RegistrosWidget

ENCABEZADOS_ALQUILERES = [
    "Cliente",
    "Desde",
    "Hasta",
    "Modalidad",
    "Tarifa",
    "Horas de uso",
    "Liquidado",
    "Cobrado",
    "Saldo",
]


class IngresosWidget(RegistrosWidget):
    corregir_contrato_solicitado = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            ["Fecha", "Tipo", "Cliente", "Descripción", "Documento", "Valor"],
            "Registrar cobro o ingreso",
            "Anular ingreso",
            columna_estirable=3,
            columnas_a_la_derecha=(5,),
            parent=parent,
        )
        layout = self.layout()
        assert isinstance(layout, QVBoxLayout)

        # 1. Recuadro del contrato activo, encima de todo
        self._recuadro = QFrame()
        self._recuadro.setObjectName("avisoInformativo")
        self._contrato = QLabel()
        self._contrato.setWordWrap(True)
        boton_corregir = QPushButton("Corregir condiciones")
        boton_corregir.clicked.connect(self.corregir_contrato_solicitado)
        fila = QHBoxLayout(self._recuadro)
        fila.addWidget(self._contrato, stretch=1)
        fila.addWidget(boton_corregir)
        layout.insertWidget(0, self._recuadro)
        self._recuadro.hide()

        # 3. Historial de alquileres, al final
        titulo = QLabel("Historial de alquileres")
        titulo.setObjectName("tituloPanel")
        self._alquileres = QTableWidget(0, len(ENCABEZADOS_ALQUILERES))
        self._alquileres.setHorizontalHeaderLabels(ENCABEZADOS_ALQUILERES)
        self._alquileres.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._alquileres.verticalHeader().setVisible(False)
        self._alquileres.setAlternatingRowColors(True)
        self._alquileres.setMaximumHeight(140)
        encabezado = self._alquileres.horizontalHeader()
        encabezado.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        encabezado.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(titulo)
        layout.addWidget(self._alquileres)

    def mostrar_contrato(self, texto: str | None) -> None:
        """Texto del contrato activo, o None para ocultar el recuadro."""
        self._recuadro.setVisible(texto is not None)
        self._contrato.setText(texto or "")

    def mostrar_alquileres(self, filas: list[tuple[str, ...]]) -> None:
        self._alquileres.setRowCount(len(filas))
        for i, fila in enumerate(filas):
            for j, texto in enumerate(fila):
                self._alquileres.setItem(i, j, QTableWidgetItem(texto))
