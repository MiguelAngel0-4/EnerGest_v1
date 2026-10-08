"""
Formularios del módulo de gastos: gasto, factura y proveedor.

Ruta: src/presentation/dialogs/gasto_dialogs.py

Vistas pasivas sobre FormularioBase: leen y muestran valores; las reglas de
negocio las aplica GastoService y los errores llegan por marcar_errores().
"""

from typing import Any, NamedTuple

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QWidget,
)

from src.presentation.widgets.campo_numerico import CampoNumerico
from src.presentation.widgets.formulario_base import FormularioBase


def _selector_fecha() -> QDateEdit:
    fecha = QDateEdit()
    fecha.setCalendarPopup(True)
    fecha.setDisplayFormat("dd/MM/yyyy")
    fecha.setMaximumDate(QDate.currentDate())
    fecha.setDate(QDate.currentDate())
    return fecha


class OpcionFactura(NamedTuple):
    """Factura con saldo, tal como se ofrece en la lista."""

    id: int
    texto: str  # Ej. "FE-0042 · Filtros del Valle"
    saldo: str  # Ej. "$ 120.000"


class RegistrarGastoDialog(FormularioBase):
    """Registro de un gasto de una planta, con o sin factura."""

    nueva_factura_solicitada = Signal()

    def __init__(
        self,
        descripcion_planta: str,
        categorias: list[tuple[str, int]],
        sugerencias: dict[int, list[str]],
        unidades: list[str],
        parent: QWidget | None = None,
    ) -> None:
        """
        Args:
            categorias: (nombre, id) de las categorías activas.
            sugerencias: Descripciones sugeridas por id de categoría, por ejemplo
                las referencias de filtros de la ficha técnica de la planta.
        """
        super().__init__("Registrar gasto", parent)
        self._sugerencias = sugerencias
        self._saldos: dict[int, str] = {}

        self._fecha = _selector_fecha()
        self._categoria = QComboBox()
        for nombre, categoria_id in categorias:
            self._categoria.addItem(nombre, categoria_id)

        # Combo editable: muestra las sugerencias, pero admite escribir cualquier texto.
        self._descripcion = QComboBox()
        self._descripcion.setEditable(True)
        self._descripcion.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._descripcion.lineEdit().setPlaceholderText("Ej. Filtro de aceite Fleetguard LF3000")
        self._descripcion.setMinimumWidth(360)

        self._cantidad = CampoNumerico(decimales=2, placeholder="1")
        self._cantidad.set_valor(1)
        self._unidad = QComboBox()
        self._unidad.setEditable(True)
        self._unidad.addItems(unidades)
        fila_cantidad = QWidget()
        fila_cantidad.setObjectName("envolturaCampo")
        layout_cantidad = QHBoxLayout(fila_cantidad)
        layout_cantidad.setContentsMargins(0, 0, 0, 0)
        layout_cantidad.addWidget(self._cantidad, stretch=1)
        layout_cantidad.addWidget(self._unidad, stretch=1)

        self._valor = CampoNumerico(decimales=0, max_digitos=15, placeholder="Ej. 45.000")

        # Soporte: con factura (lo habitual en la empresa) o sin ella.
        self._con_factura = QRadioButton("Con factura")
        self._sin_factura = QRadioButton("Sin factura (compra informal)")
        self._con_factura.setChecked(True)
        grupo = QButtonGroup(self)
        grupo.addButton(self._con_factura)
        grupo.addButton(self._sin_factura)
        fila_soporte = QWidget()
        fila_soporte.setObjectName("envolturaCampo")
        layout_soporte = QHBoxLayout(fila_soporte)
        layout_soporte.setContentsMargins(0, 0, 0, 0)
        layout_soporte.addWidget(self._con_factura)
        layout_soporte.addWidget(self._sin_factura)
        layout_soporte.addStretch()

        self._factura = QComboBox()
        self._factura.setMinimumWidth(300)
        self._boton_nueva_factura = QPushButton("Nueva factura…")
        self._saldo = QLabel()
        self._saldo.setObjectName("textoSecundario")
        fila_factura = QWidget()
        fila_factura.setObjectName("envolturaCampo")
        layout_factura = QHBoxLayout(fila_factura)
        layout_factura.setContentsMargins(0, 0, 0, 0)
        layout_factura.addWidget(self._factura, stretch=1)
        layout_factura.addWidget(self._boton_nueva_factura)

        formulario = QFormLayout()
        formulario.addRow("Planta", QLabel(f"<b>{descripcion_planta}</b>"))
        formulario.addRow("Fecha", self._campo("fecha", self._fecha))
        formulario.addRow("Categoría", self._campo("categoria_id", self._categoria))
        formulario.addRow("Descripción *", self._campo("descripcion", self._descripcion))
        formulario.addRow(
            "Cantidad y unidad", self._campo("cantidad", fila_cantidad, self._cantidad)
        )
        formulario.addRow("Valor total ($) *", self._campo("valor_total", self._valor))
        formulario.addRow("Soporte", fila_soporte)
        formulario.addRow("Factura", self._campo("factura_id", fila_factura, self._factura))
        formulario.addRow("", self._saldo)
        self._armar("Registrar gasto", formulario)

        self._categoria.currentIndexChanged.connect(self._actualizar_sugerencias)
        self._factura.currentIndexChanged.connect(self._actualizar_saldo)
        self._con_factura.toggled.connect(self._al_cambiar_soporte)
        self._boton_nueva_factura.clicked.connect(self.nueva_factura_solicitada)
        self._actualizar_sugerencias()
        self.set_facturas([])

    # --- API pública ------------------------------------------------------

    def set_facturas(self, facturas: list[OpcionFactura], seleccionar: int | None = None) -> None:
        """Llena la lista de facturas con saldo; opcionalmente deja una seleccionada."""
        self._factura.blockSignals(True)
        self._factura.clear()
        self._factura.addItem("Seleccione una factura…", None)
        self._saldos = {}
        for opcion in facturas:
            # El saldo se muestra debajo de la lista, no en ella: así el texto no se corta.
            self._factura.addItem(opcion.texto, opcion.id)
            self._saldos[opcion.id] = opcion.saldo
        indice = self._factura.findData(seleccionar) if seleccionar is not None else 0
        self._factura.setCurrentIndex(max(indice, 0))
        self._factura.blockSignals(False)
        self._actualizar_saldo()

    def valores(self) -> dict[str, Any]:
        return {
            "categoria_id": self._categoria.currentData(),
            "fecha": self._fecha.date().toPython(),
            "descripcion": self._descripcion.currentText(),
            "cantidad": self._cantidad.valor() or 0.0,
            "unidad": self._unidad.currentText(),
            "valor_total": self._valor.valor_entero() or 0,
            "factura_id": self._factura.currentData() if self._con_factura.isChecked() else None,
        }

    # --- Internos ---------------------------------------------------------

    def _validar_formulario(self) -> dict[str, str]:
        if self._con_factura.isChecked() and self._factura.currentData() is None:
            return {"factura_id": "Seleccione una factura, cree una nueva o marque “Sin factura”."}
        return {}

    def _actualizar_sugerencias(self) -> None:
        texto_actual = self._descripcion.currentText()
        self._descripcion.blockSignals(True)
        self._descripcion.clear()
        self._descripcion.addItems(self._sugerencias.get(self._categoria.currentData(), []))
        self._descripcion.setCurrentText(texto_actual)  # No borra lo que ya se escribió
        self._descripcion.blockSignals(False)

    def _actualizar_saldo(self) -> None:
        factura_id = self._factura.currentData()
        self._saldo.setText(
            f"Saldo por asignar: {self._saldos[factura_id]}" if factura_id in self._saldos else ""
        )

    def _al_cambiar_soporte(self, con_factura: bool) -> None:
        self._factura.setEnabled(con_factura)
        self._boton_nueva_factura.setEnabled(con_factura)
        self._saldo.setVisible(con_factura)


class NuevaFacturaDialog(FormularioBase):
    """Registro de una factura de proveedor."""

    nuevo_proveedor_solicitado = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Nueva factura", parent)
        self._proveedor = QComboBox()
        self._proveedor.setMinimumWidth(280)
        boton_proveedor = QPushButton("Nuevo proveedor…")
        fila_proveedor = QWidget()
        fila_proveedor.setObjectName("envolturaCampo")
        layout_proveedor = QHBoxLayout(fila_proveedor)
        layout_proveedor.setContentsMargins(0, 0, 0, 0)
        layout_proveedor.addWidget(self._proveedor, stretch=1)
        layout_proveedor.addWidget(boton_proveedor)

        self._numero = QLineEdit()
        self._numero.setPlaceholderText("Ej. FE-0042")
        self._fecha = _selector_fecha()
        self._valor = CampoNumerico(decimales=0, max_digitos=15, placeholder="Ej. 300.000")
        self._observaciones = QLineEdit()

        formulario = QFormLayout()
        formulario.addRow(
            "Proveedor *", self._campo("proveedor_id", fila_proveedor, self._proveedor)
        )
        formulario.addRow("Número de factura *", self._campo("numero_factura", self._numero))
        formulario.addRow("Fecha de la factura", self._campo("fecha_factura", self._fecha))
        formulario.addRow("Valor total ($) *", self._campo("valor_total", self._valor))
        formulario.addRow("Observaciones", self._campo("observaciones", self._observaciones))
        self._armar("Nueva factura", formulario)
        boton_proveedor.clicked.connect(self.nuevo_proveedor_solicitado)

    def set_proveedores(
        self, proveedores: list[tuple[str, int]], seleccionar: int | None = None
    ) -> None:
        self._proveedor.clear()
        self._proveedor.addItem("Seleccione un proveedor…", None)
        for nombre, proveedor_id in proveedores:
            self._proveedor.addItem(nombre, proveedor_id)
        indice = self._proveedor.findData(seleccionar) if seleccionar is not None else 0
        self._proveedor.setCurrentIndex(max(indice, 0))

    def valores(self) -> dict[str, Any]:
        return {
            "proveedor_id": self._proveedor.currentData(),
            "numero_factura": self._numero.text(),
            "fecha_factura": self._fecha.date().toPython(),
            "valor_total": self._valor.valor_entero() or 0,
            "observaciones": self._observaciones.text(),
        }

    def _validar_formulario(self) -> dict[str, str]:
        if self._proveedor.currentData() is None:
            return {"proveedor_id": "Seleccione un proveedor o cree uno nuevo."}
        return {}


class NuevoProveedorDialog(FormularioBase):
    """Registro de un proveedor."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Nuevo proveedor", parent)
        self._nombre = QLineEdit()
        self._nombre.setPlaceholderText("Ej. Filtros del Valle S.A.S.")
        self._nombre.setMinimumWidth(300)
        self._nit = QLineEdit()
        self._nit.setPlaceholderText("Opcional")
        self._telefono = QLineEdit()
        self._telefono.setPlaceholderText("Opcional")

        formulario = QFormLayout()
        formulario.addRow("Nombre *", self._campo("nombre", self._nombre))
        formulario.addRow("NIT", self._campo("nit", self._nit))
        formulario.addRow("Teléfono", self._campo("telefono", self._telefono))
        self._armar("Nuevo proveedor", formulario)

    def valores(self) -> dict[str, Any]:
        return {
            "nombre": self._nombre.text(),
            "nit": self._nit.text(),
            "telefono": self._telefono.text(),
        }
