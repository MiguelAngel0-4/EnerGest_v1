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

Desde la versión 0.7.0 tiene tres secciones comerciales, que aparecen solo
cuando corresponden: Contrato (al alquilar), Venta (al vender) y Liquidación
(al sacar de "Alquilada" una planta con contrato).
"""

from collections.abc import Callable
from datetime import date
from typing import Any, NamedTuple

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QGroupBox,
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
from src.presentation.widgets.comercial_widgets import ContratoWidget, SelectorCliente


class OpcionEstado(NamedTuple):
    """Un destino posible, con lo que el usuario debe saber antes de elegirlo."""

    clave: str
    etiqueta: str
    requiere_motivo: bool
    aviso: str
    pide_horometro: bool = False
    horometro_obligatorio: bool = False
    seccion: str = ""  # "contrato", "venta" o "" (sin datos comerciales)


class VistaLiquidacion(NamedTuple):
    """Cálculo de la liquidación, ya expresado en textos y valores para mostrar."""

    detalle: str  # Ej. "12 días × $ 180.000 por día · Constructora del Pacífico"
    calculado: int
    cobrado: int


class CambiarEstadoDialog(QDialog):
    """Permite elegir el nuevo estado, el motivo y la fecha real del cambio."""

    # (clave, motivo, fecha: date, horometro: int | None). Los datos comerciales
    # se leen con datos_comerciales() al recibir la señal.
    cambio_solicitado = Signal(str, str, object, object)
    nuevo_cliente_solicitado = Signal()

    def __init__(
        self,
        descripcion_planta: str,
        estado_actual: str,
        opciones: list[OpcionEstado],
        fecha_minima: date,
        ultima_lectura: str = "",
        parent: QWidget | None = None,
        liquidador: Callable[[date], VistaLiquidacion] | None = None,
    ) -> None:
        """
        Args:
            liquidador: Si la planta está alquilada con contrato, calcula la
                liquidación para la fecha elegida (se recalcula al cambiarla).
        """
        super().__init__(parent)
        self._liquidador = liquidador
        self._valor_editado = False
        self._cobrado = 0  # Lo ya cobrado del contrato (lo informa el liquidador)
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
        layout.addWidget(self._construir_contrato())
        layout.addWidget(self._construir_venta())
        layout.addWidget(self._construir_liquidacion())
        layout.addWidget(self._aviso)
        layout.addWidget(self._error)
        layout.addLayout(botones)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)  # Crece con avisos/errores

        self._combo.currentIndexChanged.connect(self._al_cambiar_opcion)
        # El mensaje de error desaparece en cuanto el usuario empieza a corregir.
        # textEdited (y no textChanged): solo cuando ESCRIBE el usuario. Si no, el
        # reformateo automático del horómetro ("1020" -> "1.020") al perder el foco
        # ocultaría el error justo después de mostrarlo.
        self._motivo.textEdited.connect(self._error.hide)
        self._horometro.textEdited.connect(self._error.hide)
        self._fecha.dateChanged.connect(lambda _fecha: self._actualizar_liquidacion())
        self._al_cambiar_opcion()

    # ------------------------------------------------------------------ #
    # Secciones comerciales
    # ------------------------------------------------------------------ #

    def _construir_contrato(self) -> QGroupBox:
        self._contrato = ContratoWidget()
        self._contrato.nuevo_cliente_solicitado.connect(self.nuevo_cliente_solicitado)
        self._grupo_contrato = QGroupBox("Contrato de alquiler")
        layout = QVBoxLayout(self._grupo_contrato)
        layout.addWidget(self._contrato)
        return self._grupo_contrato

    def _construir_venta(self) -> QGroupBox:
        self._cliente_venta = SelectorCliente()
        self._cliente_venta.nuevo_cliente_solicitado.connect(self.nuevo_cliente_solicitado)
        self._precio = CampoNumerico(decimales=0, max_digitos=15, placeholder="Ej. 42.000.000")
        self._documento_venta = QLineEdit()
        self._documento_venta.setPlaceholderText("Factura de venta (opcional)")
        self._grupo_venta = QGroupBox("Venta")
        formulario = QFormLayout(self._grupo_venta)
        formulario.addRow("Comprador *", self._cliente_venta)
        formulario.addRow("Precio de venta ($) *", self._precio)
        formulario.addRow("Documento", self._documento_venta)
        return self._grupo_venta

    def _construir_liquidacion(self) -> QGroupBox:
        self._detalle_liquidacion = QLabel()
        self._detalle_liquidacion.setWordWrap(True)
        self._valor_liquidado = CampoNumerico(decimales=0, max_digitos=15)
        self._valor_liquidado.setToolTip(
            "Valor sugerido según el contrato. Puede ajustarse si se negoció un descuento."
        )
        self._valor_liquidado.textEdited.connect(self._al_editar_valor)
        self._saldo = QLabel()
        self._saldo.setObjectName("datoSistema")
        self._cobrar_saldo = QCheckBox("Registrar el cobro del saldo ahora")
        self._cobrar_saldo.setChecked(True)
        self._documento_cobro = QLineEdit()
        self._documento_cobro.setPlaceholderText("Factura o cuenta de cobro (opcional)")
        self._cobrar_saldo.toggled.connect(self._documento_cobro.setEnabled)

        self._grupo_liquidacion = QGroupBox("Liquidación del alquiler")
        formulario = QFormLayout(self._grupo_liquidacion)
        formulario.addRow(self._detalle_liquidacion)
        formulario.addRow("Valor liquidado ($)", self._valor_liquidado)
        formulario.addRow("", self._saldo)
        formulario.addRow(self._cobrar_saldo)
        formulario.addRow("Documento", self._documento_cobro)
        return self._grupo_liquidacion

    def _al_editar_valor(self, _texto: str) -> None:
        self._valor_editado = True  # Desde aquí, cambiar la fecha no pisa el valor escrito
        self._actualizar_saldo()

    def _actualizar_liquidacion(self) -> None:
        if self._liquidador is None:
            return
        vista = self._liquidador(self._fecha.date().toPython())
        self._detalle_liquidacion.setText(vista.detalle)
        self._cobrado = vista.cobrado
        if not self._valor_editado:
            self._valor_liquidado.set_valor(vista.calculado)
        self._actualizar_saldo()

    def _actualizar_saldo(self) -> None:
        saldo = (self._valor_liquidado.valor_entero() or 0) - self._cobrado
        texto = f"Ya cobrado: $ {self._cobrado:,} · Saldo: $ {saldo:,}"
        self._saldo.setText(texto.replace(",", "."))

    def _al_cambiar_opcion(self) -> None:
        """Ajusta el formulario según el destino elegido."""
        opcion = self._opciones.get(self._combo.currentData())
        self._boton_actualizar.setEnabled(opcion is not None)
        self._error.hide()

        pide_horometro = opcion is not None and opcion.pide_horometro
        self._formulario.setRowVisible(self._fila_horometro, pide_horometro)
        seccion = opcion.seccion if opcion is not None else ""
        self._grupo_contrato.setVisible(seccion == "contrato")
        self._grupo_venta.setVisible(seccion == "venta")
        self._grupo_liquidacion.setVisible(self._liquidador is not None and opcion is not None)
        if self._liquidador is not None and opcion is not None:
            self._actualizar_liquidacion()

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
            errores = self._errores_de_formulario(opcion)
            if errores:
                self.mostrar_errores(errores)
                return
            horometro = self._horometro.valor_entero() if opcion.pide_horometro else None
            self.cambio_solicitado.emit(
                clave, self._motivo.text(), self._fecha.date().toPython(), horometro
            )

    def _errores_de_formulario(self, opcion: OpcionEstado) -> dict[str, str]:
        """Revisiones propias de la interfaz (datos que faltan) antes de enviar."""
        if opcion.seccion == "contrato":
            return self._contrato.errores_de_formulario()
        if opcion.seccion == "venta":
            errores: dict[str, str] = {}
            if self._cliente_venta.cliente_id() is None:
                errores["cliente_id"] = "Seleccione el comprador o cree un cliente nuevo."
            if not self._precio.valor_entero():
                errores["valor"] = "Escriba el precio de venta."
            return errores
        return {}

    # --- API pública ------------------------------------------------------

    def set_clientes(self, clientes: list[tuple[str, int]], seleccionar: int | None = None) -> None:
        """Llena los selectores de cliente; opcionalmente deja uno seleccionado."""
        self._contrato.set_clientes(clientes, seleccionar)
        self._cliente_venta.set_clientes(clientes, seleccionar)

    def datos_comerciales(self) -> dict[str, Any]:
        """Datos de la sección visible: contrato, venta y/o liquidación."""
        datos: dict[str, Any] = {}
        opcion = self._opciones.get(self._combo.currentData())
        if opcion is not None and opcion.seccion == "contrato":
            datos["contrato"] = self._contrato.valores()
        if opcion is not None and opcion.seccion == "venta":
            datos["venta"] = {
                "cliente_id": self._cliente_venta.cliente_id(),
                "valor": self._precio.valor_entero() or 0,
                "numero_documento": self._documento_venta.text(),
            }
        if self._liquidador is not None:
            datos["liquidacion"] = {
                "valor_liquidado": self._valor_liquidado.valor_entero() or 0,
                "cobrar_saldo": self._cobrar_saldo.isChecked(),
                "numero_documento": self._documento_cobro.text(),
            }
        return datos

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
        elif "tarifa" in errores:
            self._contrato.tarifa.setFocus()
        elif "valor_liquidado" in errores:
            self._valor_liquidado.setFocus()
        elif "valor" in errores:
            self._precio.setFocus()

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
