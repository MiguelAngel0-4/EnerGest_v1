"""
Diálogo de cambio de estado (Panel D del wireframe).

Ruta: src/presentation/dialogs/cambiar_estado_dialog.py

Solo ofrece los destinos que el controlador le entrega, es decir, las
transiciones válidas. Así el usuario nunca ve una opción que el sistema
vaya a rechazar, como pasar directamente de "Alquilada" a "Vendida".
"""

from datetime import date
from typing import NamedTuple

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class OpcionEstado(NamedTuple):
    """Un destino posible, con lo que el usuario debe saber antes de elegirlo."""

    clave: str
    etiqueta: str
    requiere_motivo: bool
    aviso: str


class CambiarEstadoDialog(QDialog):
    """Permite elegir el nuevo estado, el motivo y la fecha real del cambio."""

    cambio_solicitado = Signal(str, str, object)  # (clave, motivo, fecha: date)

    def __init__(
        self,
        descripcion_planta: str,
        estado_actual: str,
        opciones: list[OpcionEstado],
        fecha_minima: date,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cambiar estado")
        self.setModal(True)
        self._opciones = {opcion.clave: opcion for opcion in opciones}

        titulo = QLabel(f"Cambiar estado – {descripcion_planta}")
        titulo.setMinimumWidth(460)
        titulo.setObjectName("tituloPanel")
        titulo.setWordWrap(True)

        actual = QLabel(f"<b>{estado_actual}</b>")

        self._combo = QComboBox()
        self._combo.addItem("Seleccionar…", None)
        for opcion in opciones:
            self._combo.addItem(opcion.etiqueta, opcion.clave)

        self._aviso = QLabel()
        self._aviso.setObjectName("avisoInformativo")
        self._aviso.setWordWrap(True)
        self._aviso.hide()

        self._etiqueta_motivo = QLabel("Motivo")
        self._motivo = QLineEdit()
        self._motivo.setPlaceholderText("Ej. Venta a cliente, daño irreparable, sin demanda…")

        self._fecha = QDateEdit()
        self._fecha.setCalendarPopup(True)
        self._fecha.setDisplayFormat("dd/MM/yyyy")
        self._fecha.setMinimumDate(QDate(fecha_minima.year, fecha_minima.month, fecha_minima.day))
        self._fecha.setMaximumDate(QDate.currentDate())
        self._fecha.setDate(QDate.currentDate())
        self._fecha.setToolTip(
            "Fecha real del cambio. Puede ser anterior a hoy si se registra tarde, "
            "pero no anterior al último cambio de estado."
        )

        self._error = QLabel()
        self._error.setObjectName("mensajeError")
        self._error.setWordWrap(True)
        self._error.hide()

        formulario = QFormLayout()
        formulario.addRow("Estado actual:", actual)
        formulario.addRow("Nuevo estado:", self._combo)
        formulario.addRow(self._etiqueta_motivo, self._motivo)
        formulario.addRow("Fecha del cambio:", self._fecha)

        self._boton_actualizar = QPushButton("Actualizar estado")
        self._boton_actualizar.setObjectName("botonPrimario")
        self._boton_actualizar.setEnabled(False)
        self._boton_actualizar.clicked.connect(self._al_actualizar)
        boton_cancelar = QPushButton("Cancelar")
        boton_cancelar.clicked.connect(self.reject)
        botones = QHBoxLayout()
        botones.addStretch()
        botones.addWidget(boton_cancelar)
        botones.addWidget(self._boton_actualizar)

        layout = QVBoxLayout(self)
        layout.addWidget(titulo)
        layout.addLayout(formulario)
        layout.addWidget(self._aviso)
        layout.addWidget(self._error)
        layout.addLayout(botones)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)  # Crece con avisos/errores

        self._combo.currentIndexChanged.connect(self._al_cambiar_opcion)
        self._al_cambiar_opcion()

    def _al_cambiar_opcion(self) -> None:
        """Ajusta el formulario según el destino elegido."""
        opcion = self._opciones.get(self._combo.currentData())
        self._boton_actualizar.setEnabled(opcion is not None)
        self._error.hide()

        if opcion is None:
            self._etiqueta_motivo.setText("Motivo:")
            self._aviso.hide()
            return

        sufijo = "(obligatorio)" if opcion.requiere_motivo else "(opcional)"
        self._etiqueta_motivo.setText(f"Motivo {sufijo}:")
        self._aviso.setText(opcion.aviso)
        self._aviso.setVisible(bool(opcion.aviso))

    def _al_actualizar(self) -> None:
        clave = self._combo.currentData()
        if clave is not None:
            self._error.hide()
            self.cambio_solicitado.emit(clave, self._motivo.text(), self._fecha.date().toPython())

    # --- API pública ------------------------------------------------------

    def mostrar_errores(self, errores: dict[str, str]) -> None:
        """Muestra los errores de validación (motivo, fecha) y enfoca el campo."""
        self._error.setText(" ".join(errores.values()))
        self._error.show()
        if "motivo" in errores:
            self._motivo.setFocus()
        elif "fecha" in errores:
            self._fecha.setFocus()

    def confirmar(self, titulo: str, mensaje: str) -> bool:
        """Pregunta Sí/No antes de una acción irreversible."""
        respuesta = QMessageBox.question(
            self,
            titulo,
            mensaje,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,  # Opción por defecto: la segura
        )
        return respuesta == QMessageBox.StandardButton.Yes

    def mostrar_error(self, mensaje: str) -> None:
        QMessageBox.warning(self, self.windowTitle(), mensaje)
