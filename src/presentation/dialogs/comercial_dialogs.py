"""
Formularios del módulo comercial (Actividad 4.3).

Ruta: src/presentation/dialogs/comercial_dialogs.py

- NuevoClienteDialog: registro de un cliente.
- RegistrarIngresoDialog: cobro de un contrato (activo o con saldo) u otro ingreso.
- CorregirContratoDialog: condiciones de un contrato mientras está activo.
"""

from typing import Any, NamedTuple

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import QComboBox, QDateEdit, QFormLayout, QLabel, QLineEdit, QWidget

from src.presentation.widgets.campo_numerico import CampoNumerico
from src.presentation.widgets.comercial_widgets import ContratoWidget, SelectorCliente
from src.presentation.widgets.formulario_base import FormularioBase


class NuevoClienteDialog(FormularioBase):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Nuevo cliente", parent)
        self._nombre = QLineEdit()
        self._nombre.setPlaceholderText("Ej. Constructora del Pacífico S.A.S.")
        self._nombre.setMinimumWidth(300)
        self._documento = QLineEdit()
        self._documento.setPlaceholderText("NIT o cédula (opcional)")
        self._telefono = QLineEdit()
        self._telefono.setPlaceholderText("Opcional")
        formulario = QFormLayout()
        formulario.addRow("Nombre *", self._campo("nombre", self._nombre))
        formulario.addRow("NIT o cédula", self._campo("documento", self._documento))
        formulario.addRow("Teléfono", self._campo("telefono", self._telefono))
        self._armar("Nuevo cliente", formulario)

    def valores(self) -> dict[str, Any]:
        return {
            "nombre": self._nombre.text(),
            "documento": self._documento.text(),
            "telefono": self._telefono.text(),
        }


class ConceptoIngreso(NamedTuple):
    """A qué se aplica el ingreso: un contrato o "Otro ingreso" (alquiler_id None)."""

    texto: str
    alquiler_id: int | None
    detalle: str  # Ej. "Saldo pendiente: $ 1.160.000"
    descripcion_sugerida: str


class RegistrarIngresoDialog(FormularioBase):
    """Cobro de un contrato u otro ingreso de la planta."""

    nuevo_cliente_solicitado = Signal()

    def __init__(
        self,
        descripcion_planta: str,
        conceptos: list[ConceptoIngreso],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Registrar ingreso", parent)
        self._conceptos = conceptos

        self._concepto = QComboBox()
        self._concepto.setMinimumWidth(360)
        for concepto in conceptos:
            self._concepto.addItem(concepto.texto, concepto.alquiler_id)
        self._detalle = QLabel()
        self._detalle.setObjectName("textoSecundario")

        # El cliente solo se pide en "Otro ingreso": los cobros ya conocen el suyo.
        self._cliente = SelectorCliente()
        self._cliente.nuevo_cliente_solicitado.connect(self.nuevo_cliente_solicitado)
        self._etiqueta_cliente = QLabel("Cliente")

        self._fecha = QDateEdit()
        self._fecha.setCalendarPopup(True)
        self._fecha.setDisplayFormat("dd/MM/yyyy")
        self._fecha.setMaximumDate(QDate.currentDate())
        self._fecha.setDate(QDate.currentDate())
        self._descripcion = QLineEdit()
        self._documento = QLineEdit()
        self._documento.setPlaceholderText("Factura o cuenta de cobro (opcional)")
        self._valor = CampoNumerico(decimales=0, max_digitos=15, placeholder="Ej. 1.160.000")

        self._formulario = QFormLayout()
        self._formulario.addRow("Planta", QLabel(f"<b>{descripcion_planta}</b>"))
        self._formulario.addRow("Concepto", self._concepto)
        self._formulario.addRow("", self._detalle)
        self._formulario.addRow(self._etiqueta_cliente, self._cliente)
        self._formulario.addRow("Fecha", self._campo("fecha", self._fecha))
        self._formulario.addRow("Descripción *", self._campo("descripcion", self._descripcion))
        self._formulario.addRow("Documento", self._campo("numero_documento", self._documento))
        self._formulario.addRow("Valor ($) *", self._campo("valor", self._valor))
        self._armar("Registrar ingreso", self._formulario)

        self._concepto.currentIndexChanged.connect(self._al_cambiar_concepto)
        self._al_cambiar_concepto()

    def set_clientes(self, clientes: list[tuple[str, int]], seleccionar: int | None = None) -> None:
        self._cliente.set_clientes(clientes, seleccionar)

    def valores(self) -> dict[str, Any]:
        alquiler_id = self._concepto.currentData()
        return {
            "alquiler_id": alquiler_id,
            "cliente_id": self._cliente.cliente_id() if alquiler_id is None else None,
            "fecha": self._fecha.date().toPython(),
            "descripcion": self._descripcion.text(),
            "numero_documento": self._documento.text(),
            "valor": self._valor.valor_entero() or 0,
        }

    def _al_cambiar_concepto(self) -> None:
        concepto = self._conceptos[self._concepto.currentIndex()]
        self._detalle.setText(concepto.detalle)
        self._detalle.setVisible(bool(concepto.detalle))
        self._descripcion.setText(concepto.descripcion_sugerida)
        es_otro = concepto.alquiler_id is None
        self._formulario.setRowVisible(self._cliente, es_otro)


class CorregirContratoDialog(FormularioBase):
    """Condiciones de un contrato activo (antes de liquidarlo)."""

    nuevo_cliente_solicitado = Signal()

    def __init__(self, descripcion_contrato: str, parent: QWidget | None = None) -> None:
        super().__init__("Corregir condiciones del contrato", parent)
        self.contrato = ContratoWidget()
        self.contrato.nuevo_cliente_solicitado.connect(self.nuevo_cliente_solicitado)
        nota = QLabel(
            "Las condiciones se pueden corregir mientras el contrato está activo; "
            "al liquidarlo quedan fijas."
        )
        nota.setObjectName("textoSecundario")
        nota.setWordWrap(True)
        formulario = QFormLayout()
        formulario.addRow(QLabel(f"<b>{descripcion_contrato}</b>"))
        formulario.addRow(self._campo("contrato", self.contrato, self.contrato.tarifa))
        formulario.addRow(nota)
        self._armar("Corregir condiciones del contrato", formulario)

    def valores(self) -> dict[str, Any]:
        return self.contrato.valores()

    def _validar_formulario(self) -> dict[str, str]:
        errores = self.contrato.errores_de_formulario()
        return {"contrato": " ".join(errores.values())} if errores else {}
