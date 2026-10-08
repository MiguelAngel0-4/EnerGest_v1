"""
Base de las pestañas de la ficha que listan registros anulables.

Ruta: src/presentation/widgets/registros_widget.py

Gastos y mantenimientos comparten la misma forma: botones Registrar y
Anular, casilla "Mostrar anulados", tabla con los anulados tachados y un
resumen al pie. Esta base reúne esa forma; cada pestaña solo define sus
columnas y textos.
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

_COLOR_ANULADO = "#8A939B"
_A_LA_DERECHA = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


class FilaRegistro(NamedTuple):
    """Fila genérica: id del registro y textos ya formateados de cada columna."""

    id: int
    textos: tuple[str, ...]
    anulado: bool = False
    motivo_anulacion: str | None = None


class RegistrosWidget(QWidget):
    """Lista de registros con acciones Registrar / Anular y resumen."""

    registrar_solicitado = Signal()
    anular_solicitado = Signal(int)
    mostrar_anulados_cambiado = Signal(bool)

    def __init__(
        self,
        encabezados: list[str],
        texto_registrar: str,
        texto_anular: str,
        columna_estirable: int,
        columnas_a_la_derecha: tuple[int, ...] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._texto_anular = texto_anular
        self._a_la_derecha = columnas_a_la_derecha

        self._boton_registrar = QPushButton(texto_registrar)
        self._boton_registrar.setObjectName("botonPrimario")
        self._boton_anular = QPushButton(texto_anular)
        self._ver_anulados = QCheckBox("Mostrar anulados")

        self._aviso = QLabel()
        self._aviso.setObjectName("avisoInformativo")
        self._aviso.setWordWrap(True)
        self._aviso.hide()

        self._tabla = QTableWidget(0, len(encabezados))
        self._tabla.setHorizontalHeaderLabels(encabezados)
        self._tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tabla.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tabla.setAlternatingRowColors(True)
        self._tabla.verticalHeader().setVisible(False)
        encabezado = self._tabla.horizontalHeader()
        encabezado.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        encabezado.setSectionResizeMode(columna_estirable, QHeaderView.ResizeMode.Stretch)

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

    def mostrar_filas(self, filas: list[FilaRegistro]) -> None:
        self._tabla.setRowCount(len(filas))
        for i, fila in enumerate(filas):
            for j, texto in enumerate(fila.textos):
                celda = QTableWidgetItem(texto)
                celda.setData(Qt.ItemDataRole.UserRole, fila.id)
                if j in self._a_la_derecha:  # Números alineados a la derecha
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

    def registro_seleccionado(self) -> int | None:
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
        registro_id = self.registro_seleccionado()
        if registro_id is None:
            self.mostrar_info(
                self._texto_anular, "Seleccione primero el registro que desea anular."
            )
            return
        self.anular_solicitado.emit(registro_id)
