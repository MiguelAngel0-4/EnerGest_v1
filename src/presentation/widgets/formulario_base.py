"""
Base común para los formularios modales con errores por campo.

Ruta: src/presentation/widgets/formulario_base.py

Reúne la mecánica que comparten los formularios: cada campo lleva debajo
una etiqueta de error (oculta hasta que hace falta), el borde se pinta de
rojo y el diálogo crece lo necesario para mostrar los mensajes completos.

Es como un formato impreso con las casillas ya dibujadas: cada formulario
nuevo solo decide qué casillas lleva, no cómo se marcan los errores.
"""

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def marcar_error(widget: QWidget, con_error: bool) -> None:
    """Activa la propiedad "error" que la hoja de estilos pinta con borde rojo."""
    widget.setProperty("error", con_error)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class FormularioBase(QDialog):
    """Diálogo con campos, errores por campo y botones Cancelar / Guardar."""

    guardar_solicitado = Signal(object)  # dict[str, Any]

    def __init__(self, titulo: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setModal(True)
        self._campos: dict[str, tuple[QWidget, QLabel]] = {}
        self._mensaje_general = QLabel()
        self._mensaje_general.setObjectName("mensajeError")
        self._mensaje_general.setWordWrap(True)
        self._mensaje_general.hide()

    # --- Para las subclases -------------------------------------------------

    def valores(self) -> dict[str, Any]:
        """Lee el formulario. Cada subclase lo implementa."""
        raise NotImplementedError

    def _validar_formulario(self) -> dict[str, str]:
        """
        Revisiones propias de la interfaz (no reglas de negocio), por ejemplo
        "marcó Con factura pero no eligió ninguna". Por defecto, ninguna.
        """
        return {}

    def _campo(self, nombre: str, contenedor: QWidget, resaltar: QWidget | None = None) -> QWidget:
        """Envuelve un control con su etiqueta de error."""
        etiqueta = QLabel()
        etiqueta.setObjectName("errorCampo")
        etiqueta.setWordWrap(True)
        etiqueta.hide()
        envoltura = QWidget()
        envoltura.setObjectName("envolturaCampo")
        layout = QVBoxLayout(envoltura)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(contenedor)
        layout.addWidget(etiqueta)
        self._campos[nombre] = (resaltar or contenedor, etiqueta)
        return envoltura

    def _armar(self, encabezado: str, contenido: QLayout, texto_guardar: str = "Guardar") -> None:
        """Ensambla título, mensaje general, contenido y botones."""
        titulo = QLabel(encabezado)
        titulo.setObjectName("tituloPanel")
        boton_guardar = QPushButton(texto_guardar)
        boton_guardar.setObjectName("botonPrimario")
        boton_guardar.setDefault(True)
        boton_guardar.clicked.connect(self._al_guardar)
        boton_cancelar = QPushButton("Cancelar")
        boton_cancelar.clicked.connect(self.reject)
        botones = QHBoxLayout()
        botones.addStretch()
        botones.addWidget(boton_cancelar)
        botones.addWidget(boton_guardar)

        layout = QVBoxLayout(self)
        layout.addWidget(titulo)
        layout.addWidget(self._mensaje_general)
        layout.addLayout(contenido)
        layout.addLayout(botones)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)  # Crece con los errores

    # --- API pública ----------------------------------------------------------

    def marcar_errores(self, errores: dict[str, str]) -> None:
        """Pinta en rojo cada campo con error y muestra su mensaje debajo."""
        self.limpiar_errores()
        sin_campo: list[str] = []
        primero: QWidget | None = None
        for nombre, mensaje in errores.items():
            if nombre not in self._campos:
                sin_campo.append(mensaje)
                continue
            control, etiqueta = self._campos[nombre]
            etiqueta.setText(mensaje)
            etiqueta.show()
            marcar_error(control, True)
            primero = primero or control
        self._mensaje_general.setText(" ".join(["Revise los campos marcados en rojo.", *sin_campo]))
        self._mensaje_general.show()
        if primero is not None:
            primero.setFocus()

    def limpiar_errores(self) -> None:
        self._mensaje_general.hide()
        for control, etiqueta in self._campos.values():
            etiqueta.hide()
            marcar_error(control, False)

    def mostrar_error(self, mensaje: str) -> None:
        QMessageBox.warning(self, self.windowTitle(), mensaje)

    def _al_guardar(self) -> None:
        self.limpiar_errores()
        errores = self._validar_formulario()
        if errores:
            self.marcar_errores(errores)
            return
        self.guardar_solicitado.emit(self.valores())
