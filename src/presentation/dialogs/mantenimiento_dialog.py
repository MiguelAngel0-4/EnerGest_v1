"""
Formulario "Registrar mantenimiento" (Actividad 4.2).

Ruta: src/presentation/dialogs/mantenimiento_dialog.py

Tres partes:
1. Datos del mantenimiento (fecha, tipo, horómetro, técnico, trabajo).
2. Próximo mantenimiento: por fecha, por horas o ambas. En los preventivos se
   sugiere solo (+6 meses / +250 h) apenas se escribe el horómetro.
3. Insumos y mano de obra: tabla editable. "Cargar insumos de la ficha técnica"
   llena las líneas con los filtros y el aceite de la planta; solo faltan los valores.
"""

import re
from collections.abc import Callable
from datetime import date
from typing import Any

from PySide6.QtCore import (
    QAbstractItemModel,
    QDate,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.presentation.widgets.campo_numerico import CampoNumerico
from src.presentation.widgets.formulario_base import FormularioBase
from src.presentation.widgets.selector_factura import OpcionFactura, SelectorFactura

# Columnas de la tabla de insumos
_CATEGORIA, _DESCRIPCION, _CANTIDAD, _UNIDAD, _VALOR = range(5)
_ENCABEZADOS = ["Categoría", "Descripción", "Cantidad", "Unidad", "Valor ($)"]
_PREVENTIVO = "PREVENTIVO"

# (categoria_id, descripción, cantidad, unidad): insumo sugerido desde la ficha técnica
InsumoSugerido = tuple[int, str, float, str | None]
Sugeridor = Callable[[date, int], tuple[date, int]]


class _DelegadoNumerico(QStyledItemDelegate):
    """Editor de celda numérico: la misma escritura que CampoNumerico (coma o punto)."""

    def __init__(self, decimales: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._decimales = decimales

    def createEditor(  # Nombre impuesto por Qt
        self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex
    ) -> QWidget:
        return CampoNumerico(decimales=self._decimales, max_digitos=12, parent=parent)

    def setEditorData(self, editor: QWidget, index: QModelIndex) -> None:
        if isinstance(editor, CampoNumerico):
            editor.set_valor(_numero(str(index.data() or ""), self._decimales))

    def setModelData(
        self,
        editor: QWidget,
        model: QAbstractItemModel,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        if isinstance(editor, CampoNumerico):
            editor.set_valor(editor.valor())  # Normaliza el formato (miles, coma decimal)
            model.setData(index, editor.text())


def _numero(texto: str, decimales: int) -> float | None:
    """Convierte el texto de una celda en número ("1.250" -> 1250; "2,5" -> 2.5)."""
    texto = texto.strip()
    if not texto:
        return None
    if decimales == 0:
        digitos = re.sub(r"\D", "", texto)
        return float(digitos) if digitos else None
    try:
        return float(texto.replace(".", "").replace(",", ".")) if "," in texto else float(texto)
    except ValueError:
        return None


class RegistrarMantenimientoDialog(FormularioBase):
    """Registro de un mantenimiento con sus insumos."""

    nueva_factura_solicitada = Signal()

    def __init__(
        self,
        descripcion_planta: str,
        ultima_lectura: str,
        tipos: list[tuple[str, str]],
        tecnicos: list[str],
        categorias: list[tuple[str, int]],
        insumos_ficha: list[InsumoSugerido],
        unidades: list[str],
        sugeridor: Sugeridor | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Registrar mantenimiento", parent)
        self._categorias = {categoria_id: nombre for nombre, categoria_id in categorias}
        self._insumos_ficha = insumos_ficha
        self._unidades = unidades
        self._sugeridor = sugeridor

        contenido = QVBoxLayout()
        contenido.addWidget(self._grupo_datos(tipos, tecnicos, ultima_lectura))
        contenido.addWidget(self._grupo_insumos(categorias))
        soporte = QFormLayout()
        self._soporte = SelectorFactura(compacto=True)
        soporte.addRow("Soporte", self._campo("factura_id", self._soporte, self._soporte.combo))
        contenido.addLayout(soporte)
        self._armar(f"Registrar mantenimiento – {descripcion_planta}", contenido)

        self._tipo.currentIndexChanged.connect(self._sugerir_si_corresponde)
        self._horometro.editingFinished.connect(self._sugerir_si_corresponde)
        self._soporte.nueva_factura_solicitada.connect(self.nueva_factura_solicitada)
        self._tabla.itemChanged.connect(self._al_cambiar_celda)
        self._actualizar_total()

    # ------------------------------------------------------------------ #
    # Construcción
    # ------------------------------------------------------------------ #

    def _grupo_datos(
        self, tipos: list[tuple[str, str]], tecnicos: list[str], ultima_lectura: str
    ) -> QGroupBox:
        self._fecha = QDateEdit()
        self._fecha.setCalendarPopup(True)
        self._fecha.setDisplayFormat("dd/MM/yyyy")
        self._fecha.setMaximumDate(QDate.currentDate())
        self._fecha.setDate(QDate.currentDate())

        self._tipo = QComboBox()
        for texto, clave in tipos:
            self._tipo.addItem(texto, clave)

        # Horómetro: obligatorio y sin pre-llenar, para que se lea del equipo real.
        self._horometro = CampoNumerico(decimales=0, placeholder="Lectura actual")
        referencia = QLabel(f"Última lectura registrada: {ultima_lectura}")
        referencia.setObjectName("textoSecundario")
        fila_horometro = QWidget()
        fila_horometro.setObjectName("envolturaCampo")
        layout_horometro = QVBoxLayout(fila_horometro)
        layout_horometro.setContentsMargins(0, 0, 0, 0)
        layout_horometro.setSpacing(2)
        layout_horometro.addWidget(self._horometro)
        layout_horometro.addWidget(referencia)

        self._tecnico = QComboBox()
        self._tecnico.setEditable(True)
        self._tecnico.addItems(tecnicos)
        self._tecnico.setCurrentIndex(-1)
        self._tecnico.lineEdit().setPlaceholderText("Nombre del técnico")

        self._descripcion = QPlainTextEdit()
        self._descripcion.setFixedHeight(46)
        self._descripcion.setPlaceholderText("Ej. Cambio de aceite, filtros y revisión de baterías")

        grilla = QGridLayout()
        grilla.addWidget(QLabel("Fecha"), 0, 0)
        grilla.addWidget(self._campo("fecha", self._fecha), 0, 1)
        grilla.addWidget(QLabel("Tipo"), 0, 2)
        grilla.addWidget(self._tipo, 0, 3)
        grilla.addWidget(QLabel("Horómetro (h) *"), 1, 0, Qt.AlignmentFlag.AlignTop)
        grilla.addWidget(self._campo("horometro", fila_horometro, self._horometro), 1, 1)
        grilla.addWidget(QLabel("Técnico"), 1, 2, Qt.AlignmentFlag.AlignTop)
        grilla.addWidget(self._tecnico, 1, 3, Qt.AlignmentFlag.AlignTop)
        grilla.addWidget(QLabel("Trabajo realizado *"), 2, 0, Qt.AlignmentFlag.AlignTop)
        grilla.addWidget(self._campo("descripcion", self._descripcion), 2, 1, 1, 3)
        grilla.addWidget(QLabel("Próximo"), 3, 0)
        grilla.addWidget(self._fila_proximo(), 3, 1, 1, 3)
        grilla.setColumnStretch(1, 1)
        grilla.setColumnStretch(3, 1)
        grupo = QGroupBox("Datos del mantenimiento")
        grupo.setLayout(grilla)
        return grupo

    def _fila_proximo(self) -> QWidget:
        """Próximo mantenimiento: por fecha, por horas o ambas (lo que ocurra primero)."""
        self._programar_fecha = QCheckBox("Fecha")
        self._proxima_fecha = QDateEdit()
        self._proxima_fecha.setCalendarPopup(True)
        self._proxima_fecha.setDisplayFormat("dd/MM/yyyy")
        self._proxima_fecha.setDate(QDate.currentDate().addMonths(6))
        self._proxima_fecha.setEnabled(False)
        self._programar_fecha.toggled.connect(self._proxima_fecha.setEnabled)
        self._proximo_horometro = CampoNumerico(decimales=0, placeholder="Horas (opcional)")

        boton_sugerir = QPushButton("Sugerir")
        boton_sugerir.setToolTip(
            "Calcula el próximo preventivo a partir de la fecha y el horómetro"
        )
        boton_sugerir.clicked.connect(lambda: self._sugerir(forzar=True))
        boton_sugerir.setVisible(self._sugeridor is not None)

        fila = QWidget()
        fila.setObjectName("envolturaCampo")
        layout = QHBoxLayout(fila)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._programar_fecha)
        layout.addWidget(self._campo("proxima_fecha", self._proxima_fecha), stretch=1)
        layout.addWidget(QLabel("o a las"))
        layout.addWidget(self._campo("proximo_horometro", self._proximo_horometro), stretch=1)
        layout.addWidget(QLabel("h"))
        layout.addWidget(boton_sugerir)
        return fila

    def _grupo_insumos(self, categorias: list[tuple[str, int]]) -> QGroupBox:
        self._categoria_nueva = QComboBox()
        for nombre, categoria_id in categorias:
            self._categoria_nueva.addItem(nombre, categoria_id)
        boton_agregar = QPushButton("Agregar línea")
        boton_cargar = QPushButton("Cargar insumos de la ficha técnica")
        boton_quitar = QPushButton("Quitar línea")
        if not self._insumos_ficha:
            boton_cargar.setEnabled(False)
            boton_cargar.setToolTip("La ficha técnica de esta planta no tiene filtros ni aceite")
        boton_agregar.clicked.connect(
            lambda: self.agregar_linea(self._categoria_nueva.currentData())
        )
        boton_cargar.clicked.connect(self.cargar_insumos_ficha)
        boton_quitar.clicked.connect(self._quitar_linea)

        self._tabla = QTableWidget(0, len(_ENCABEZADOS))
        self._tabla.setHorizontalHeaderLabels(_ENCABEZADOS)
        self._tabla.verticalHeader().setVisible(False)
        self._tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tabla.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self._tabla.setItemDelegateForColumn(_CANTIDAD, _DelegadoNumerico(2, self._tabla))
        self._tabla.setItemDelegateForColumn(_VALOR, _DelegadoNumerico(0, self._tabla))
        encabezado = self._tabla.horizontalHeader()
        encabezado.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        encabezado.setSectionResizeMode(_DESCRIPCION, QHeaderView.ResizeMode.Stretch)
        self._tabla.setMinimumSize(720, 128)
        self._tabla.verticalHeader().setDefaultSectionSize(26)

        self._total = QLabel()
        self._total.setObjectName("datoSistema")
        nota = QLabel("Doble clic para editar. Cada línea se guarda como gasto.")
        nota.setObjectName("textoSecundario")

        acciones = QHBoxLayout()
        acciones.addWidget(self._categoria_nueva)
        acciones.addWidget(boton_agregar)
        acciones.addWidget(boton_cargar)
        acciones.addStretch()
        acciones.addWidget(boton_quitar)
        pie = QHBoxLayout()
        pie.addWidget(nota)
        pie.addStretch()
        pie.addWidget(self._total)

        layout = QVBoxLayout()
        layout.addLayout(acciones)
        layout.addWidget(self._campo("insumos", self._tabla))
        layout.addLayout(pie)
        grupo = QGroupBox("Insumos y mano de obra")
        grupo.setLayout(layout)
        return grupo

    # ------------------------------------------------------------------ #
    # API pública
    # ------------------------------------------------------------------ #

    def agregar_linea(
        self,
        categoria_id: int,
        descripcion: str = "",
        cantidad: float = 1.0,
        unidad: str | None = None,
    ) -> None:
        """Agrega una fila; la categoría queda fija y lo demás se puede editar."""
        fila = self._tabla.rowCount()
        self._tabla.blockSignals(True)
        self._tabla.insertRow(fila)
        categoria = QTableWidgetItem(self._categorias.get(categoria_id, ""))
        categoria.setData(Qt.ItemDataRole.UserRole, categoria_id)
        categoria.setFlags(categoria.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._tabla.setItem(fila, _CATEGORIA, categoria)
        self._tabla.setItem(fila, _DESCRIPCION, QTableWidgetItem(descripcion))
        cantidad_texto = f"{cantidad:g}".replace(".", ",")
        self._tabla.setItem(fila, _CANTIDAD, QTableWidgetItem(cantidad_texto))
        self._tabla.setItem(fila, _UNIDAD, QTableWidgetItem(unidad or self._unidades[0]))
        self._tabla.setItem(fila, _VALOR, QTableWidgetItem(""))
        self._tabla.blockSignals(False)
        self._actualizar_total()

    def cargar_insumos_ficha(self) -> None:
        """Agrega los filtros y el aceite de la ficha técnica: solo faltan los valores."""
        for categoria_id, descripcion, cantidad, unidad in self._insumos_ficha:
            self.agregar_linea(categoria_id, descripcion, cantidad, unidad)

    def escribir_celda(self, fila: int, columna: int, texto: str) -> None:
        """Escribe en una celda (útil para pruebas y para cargar datos)."""
        self._tabla.item(fila, columna).setText(texto)

    def set_facturas(self, facturas: list[OpcionFactura], seleccionar: int | None = None) -> None:
        self._soporte.set_facturas(facturas, seleccionar)

    def valores(self) -> dict[str, Any]:
        insumos = self._insumos()
        return {
            "fecha": self._fecha.date().toPython(),
            "tipo": self._tipo.currentData(),
            "horometro": self._horometro.valor_entero(),
            "tecnico": self._tecnico.currentText(),
            "descripcion": self._descripcion.toPlainText(),
            "proxima_fecha": (
                self._proxima_fecha.date().toPython() if self._programar_fecha.isChecked() else None
            ),
            "proximo_horometro": self._proximo_horometro.valor_entero(),
            "insumos": insumos,
            # Sin líneas no hay nada que respaldar con una factura.
            "factura_id": self._soporte.factura_id() if insumos else None,
        }

    # ------------------------------------------------------------------ #
    # Internos
    # ------------------------------------------------------------------ #

    def _insumos(self) -> list[dict[str, Any]]:
        lineas: list[dict[str, Any]] = []
        for fila in range(self._tabla.rowCount()):
            lineas.append(
                {
                    "categoria_id": self._tabla.item(fila, _CATEGORIA).data(
                        Qt.ItemDataRole.UserRole
                    ),
                    "descripcion": self._texto(fila, _DESCRIPCION),
                    "cantidad": _numero(self._texto(fila, _CANTIDAD), 2) or 0.0,
                    "unidad": self._texto(fila, _UNIDAD),
                    "valor_total": int(_numero(self._texto(fila, _VALOR), 0) or 0),
                }
            )
        return lineas

    def _texto(self, fila: int, columna: int) -> str:
        celda = self._tabla.item(fila, columna)
        return celda.text() if celda is not None else ""

    def _validar_formulario(self) -> dict[str, str]:
        errores: dict[str, str] = {}
        if self._horometro.valor_entero() is None:
            errores["horometro"] = "La lectura del horómetro es obligatoria."
        if self._tabla.rowCount() and self._soporte.falta_seleccion():
            errores["factura_id"] = (
                "Seleccione la factura de los insumos, cree una nueva o marque “Sin factura”."
            )
        return errores

    def _al_cambiar_celda(self, celda: QTableWidgetItem) -> None:
        """Muestra los números con formato colombiano: 45000 -> 45.000; 3.5 -> 3,5."""
        decimales = {_CANTIDAD: 2, _VALOR: 0}.get(celda.column())
        if decimales is not None:
            numero = _numero(celda.text(), decimales)
            if numero is not None:
                campo = CampoNumerico(decimales=decimales)
                campo.set_valor(numero)
                if campo.text() != celda.text():
                    self._tabla.blockSignals(True)  # Evita volver a entrar aquí
                    celda.setText(campo.text())
                    self._tabla.blockSignals(False)
        self._actualizar_total()

    def _quitar_linea(self) -> None:
        fila = self._tabla.currentRow()
        if fila >= 0:
            self._tabla.removeRow(fila)
            self._actualizar_total()

    def _actualizar_total(self) -> None:
        total = sum(linea["valor_total"] for linea in self._insumos())
        cantidad = self._tabla.rowCount()
        self._total.setText(
            f"Total insumos: $ {total:,}".replace(",", ".") + f" ({cantidad} línea(s))"
        )

    def _sugerir_si_corresponde(self) -> None:
        """En los preventivos, sugiere el próximo si el usuario aún no lo definió."""
        vacio = not self._programar_fecha.isChecked() and self._proximo_horometro.valor() is None
        if self._tipo.currentData() == _PREVENTIVO and vacio:
            self._sugerir(forzar=False)

    def _sugerir(self, forzar: bool) -> None:
        horometro = self._horometro.valor_entero()
        if self._sugeridor is None or horometro is None:
            return
        fecha, horas = self._sugeridor(self._fecha.date().toPython(), horometro)
        if forzar or self._proximo_horometro.valor() is None:
            self._proximo_horometro.set_valor(horas)
        self._programar_fecha.setChecked(True)
        self._proxima_fecha.setDate(QDate(fecha.year, fecha.month, fecha.day))
