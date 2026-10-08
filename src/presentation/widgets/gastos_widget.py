"""
Pestaña "Gastos" de la ficha de una planta.

Ruta: src/presentation/widgets/gastos_widget.py

Vista pasiva: muestra filas ya formateadas y avisa con señales lo que el
usuario pide (registrar, anular, ver anulados). No conoce los servicios.
"""

from typing import NamedTuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

_ENCABEZADOS = ["Fecha", "Categoría", "Descripción", "Cantidad", "Valor", "Soporte"]
_COLOR_ANULADO = "#8A939B"
_A_LA_DERECHA = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


class FilaGasto(NamedTuple):
    """Una fila de la tabla, con los textos ya formateados por el controlador."""

    id: int
    fecha: str
    categoria: str
    descripcion: str
    cantidad: str
    valor: str
    soporte: str
    anulado: bool = False
    motivo_anulacion: str | None = None


class GastosWidget(QWidget):
    """Lista de gastos de una planta con sus acciones y totales."""

    registrar_solicitado = Signal()
    anular_solicitado = Signal(int)  # id del gasto
    mostrar_anulados_cambiado = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._boton_registrar = QPushButton("Registrar gasto")
        self._boton_registrar.setObjectName("botonPrimario")
        self._boton_anular = QPushButton("Anular gasto")
        self._ver_anulados = QCheckBox("Mostrar anulados")

        self._aviso = QLabel()
        self._aviso.setObjectName("avisoInformativo")
        self._aviso.setWordWrap(True)
        self._aviso.hide()

        self._tabla = QTableWidget(0, len(_ENCABEZADOS))
        self._tabla.setHorizontalHeaderLabels(_ENCABEZADOS)
        self._tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tabla.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tabla.setAlternatingRowColors(True)
        self._tabla.verticalHeader().setVisible(False)
        encabezado = self._tabla.horizontalHeader()
        encabezado.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        encabezado.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # Descripción

        self._resumen = QLabel()
        self._resumen.setObjectName("datoSistema")
        self._resumen.setWordWrap(True)

        acciones = QHBoxLayout()
        acciones.addWidget(self._boton_registrar)
        acciones.addWidget(self._boton_anular)
        acciones.addStretch()
        acciones.addWidget(self._ver_anulados)

        layout = QVBoxLayout(self)
        layout.addLayout(acciones)
        layout.addWidget(self._aviso)
        layout.addWidget(self._tabla, stretch=1)
        layout.addWidget(self._resumen)

        self._boton_registrar.clicked.connect(self.registrar_solicitado)
        self._boton_anular.clicked.connect(self._al_anular)
        self._ver_anulados.toggled.connect(self.mostrar_anulados_cambiado)

    # --- API pública ------------------------------------------------------

    def mostrar_gastos(self, filas: list[FilaGasto]) -> None:
        self._tabla.setRowCount(len(filas))
        for i, fila in enumerate(filas):
            textos = [
                fila.fecha,
                fila.categoria,
                fila.descripcion,
                fila.cantidad,
                fila.valor,
                fila.soporte,
            ]
            for j, texto in enumerate(textos):
                celda = QTableWidgetItem(texto)
                celda.setData(Qt.ItemDataRole.UserRole, fila.id)
                if j in (3, 4):  # Cantidad y valor, alineados a la derecha como en contabilidad
                    celda.setTextAlignment(_A_LA_DERECHA)
                if fila.anulado:
                    # Tachado y gris: el error queda visible, como en contabilidad.
                    fuente = celda.font()
                    fuente.setStrikeOut(True)
                    celda.setFont(fuente)
                    celda.setForeground(QBrush(QColor(_COLOR_ANULADO)))
                    celda.setToolTip(f"Anulado: {fila.motivo_anulacion}")
                self._tabla.setItem(i, j, celda)

    def mostrar_resumen(self, texto: str) -> None:
        self._resumen.setText(texto)

    def deshabilitar_registro(self, motivo: str) -> None:
        """Para plantas vendidas o dadas de baja: se consulta, pero no se registra."""
        self._boton_registrar.setEnabled(False)
        self._aviso.setText(motivo)
        self._aviso.show()

    def gasto_seleccionado(self) -> int | None:
        fila = self._tabla.currentRow()
        if fila < 0 or self._tabla.item(fila, 0) is None:
            return None
        return int(self._tabla.item(fila, 0).data(Qt.ItemDataRole.UserRole))

    def pedir_motivo(self, titulo: str, mensaje: str) -> str | None:
        texto, aceptado = QInputDialog.getText(self, titulo, mensaje)
        return texto if aceptado else None

    def mostrar_info(self, titulo: str, mensaje: str) -> None:
        QMessageBox.information(self, titulo, mensaje)

    def mostrar_error(self, titulo: str, mensaje: str) -> None:
        QMessageBox.warning(self, titulo, mensaje)

    def _al_anular(self) -> None:
        gasto_id = self.gasto_seleccionado()
        if gasto_id is None:
            self.mostrar_info("Anular gasto", "Seleccione primero el gasto que desea anular.")
            return
        self.anular_solicitado.emit(gasto_id)
