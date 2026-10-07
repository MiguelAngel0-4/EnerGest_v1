"""
Diálogo de cambio de estado (Panel D del wireframe).

Ruta: src/presentation/dialogs/cambiar_estado_dialog.py

Solo ofrece los destinos que el controlador le entrega, es decir, las
transiciones válidas. Así el usuario nunca ve una opción que el sistema
vaya a rechazar, como pasar directamente de "Alquilada" a "Vendida".

La lectura del horómetro aparece solo cuando aplica: obligatoria al pasar a
"Alquilada" y opcional al regresar del alquiler. El campo NO se pre-llena:
se muestra la última lectura como referencia, para que el usuario vaya a
mirar el horómetro real en lugar de aceptar un valor por inercia.
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

from src.presentation.widgets.campo_numerico import CampoNumerico


class OpcionEstado(NamedTuple):
    """Un destino posible, con lo que el usuario debe saber antes de elegirlo."""

    clave: str
    etiqueta: str
    requiere_motivo: bool
    aviso: str
    pide_horometro: bool = False
    horometro_obligatorio: bool = False


class CambiarEstadoDialog(QDialog):
    """Permite elegir el nuevo estado, el motivo y la fecha real del cambio."""

    # (clave, motivo, fecha: date, horometro: int | None)
    cambio_solicitado = Signal(str, str, object, object)

    def __init__(
        self,
        descripcion_planta: str,
        estado_actual: str,
        opciones: list[OpcionEstado],
        fecha_minima: date,
        ultima_lectura: str = "",
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

        self._etiqueta_horometro = QLabel("Lectura del horómetro (h):")
        self._horometro = CampoNumerico(decimales=0, placeholder="Lectura actual")
        self._referencia_horometro = QLabel(f"Última lectura registrada: {ultima_lectura}")
        self._referencia_horometro.setObjectName("textoSecundario")
        fila_horometro = QWidget()
        fila_horometro.setObjectName("envolturaCampo")
        layout_horometro = QVBoxLayout(fila_horometro)
        layout_horometro.setContentsMargins(0, 0, 0, 0)
        layout_horometro.setSpacing(2)
        layout_horometro.addWidget(self._horometro)
        layout_horometro.addWidget(self._referencia_horometro)

        self._error = QLabel()
        self._error.setObjectName("mensajeError")
        self._error.setWordWrap(True)
        self._error.hide()

        self._formulario = QFormLayout()
        self._formulario.addRow("Estado actual:", actual)
        self._formulario.addRow("Nuevo estado:", self._combo)
        self._formulario.addRow(self._etiqueta_motivo, self._motivo)
        self._formulario.addRow(self._etiqueta_horometro, fila_horometro)
        self._formulario.addRow("Fecha del cambio:", self._fecha)
        self._fila_horometro = fila_horometro

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
        layout.addLayout(self._formulario)
        layout.addWidget(self._aviso)
        layout.addWidget(self._error)
        layout.addLayout(botones)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)  # Crece con avisos/errores

        self._combo.currentIndexChanged.connect(self._al_cambiar_opcion)
        # El mensaje de error desaparece en cuanto el usuario empieza a corregir.
        self._motivo.textChanged.connect(self._error.hide)
        self._horometro.textChanged.connect(self._error.hide)
        self._al_cambiar_opcion()

    def _al_cambiar_opcion(self) -> None:
        """Ajusta el formulario según el destino elegido."""
        opcion = self._opciones.get(self._combo.currentData())
        self._boton_actualizar.setEnabled(opcion is not None)
        self._error.hide()

        pide_horometro = opcion is not None and opcion.pide_horometro
        self._formulario.setRowVisible(self._fila_horometro, pide_horometro)

        if opcion is None:
            self._etiqueta_motivo.setText("Motivo:")
            self._aviso.hide()
            return

        sufijo_horometro = "obligatoria" if opcion.horometro_obligatorio else "opcional"
        self._etiqueta_horometro.setText(f"Lectura del horómetro (h, {sufijo_horometro}):")

        sufijo = "(obligatorio)" if opcion.requiere_motivo else "(opcional)"
        self._etiqueta_motivo.setText(f"Motivo {sufijo}:")
        self._aviso.setText(opcion.aviso)
        self._aviso.setVisible(bool(opcion.aviso))

    def _al_actualizar(self) -> None:
        clave = self._combo.currentData()
        if clave is not None:
            self._error.hide()
            opcion = self._opciones[clave]
            horometro = self._horometro.valor_entero() if opcion.pide_horometro else None
            self.cambio_solicitado.emit(
                clave, self._motivo.text(), self._fecha.date().toPython(), horometro
            )

    # --- API pública ------------------------------------------------------

    def mostrar_errores(self, errores: dict[str, str]) -> None:
        """Muestra los errores de validación (motivo, fecha) y enfoca el campo."""
        self._error.setText(" ".join(errores.values()))
        self._error.show()
        if "motivo" in errores:
            self._motivo.setFocus()
        elif "horometro" in errores:
            self._horometro.setFocus()
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
