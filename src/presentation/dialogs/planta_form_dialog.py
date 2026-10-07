"""
Formulario de registro y edición de plantas (Panel C del wireframe).

Ruta: src/presentation/dialogs/planta_form_dialog.py

Vista pasiva: no valida reglas de negocio ni guarda nada. Al pulsar
"Guardar" emite guardar_solicitado(valores) y espera a que el controlador
responda: si hay errores, los marca en rojo campo por campo; si todo salió
bien, el controlador cierra el diálogo.

Las claves del diccionario de valores son los mismos nombres de campo de
DatosPlanta. Así, los errores del servicio ({"potencia_kva": "..."})
se pueden ubicar directamente en el campo correspondiente.

Los campos numéricos usan CampoNumerico (no QSpinBox): ver la explicación
del defecto corregido en src/presentation/widgets/campo_numerico.py.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QDateEdit,
    QDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.presentation.widgets.campo_numerico import CampoNumerico

# Campos de referencia de filtros: nombre en DatosPlanta -> etiqueta visible.
CAMPOS_FILTROS: dict[str, str] = {
    "filtro_aceite": "Filtro de aceite",
    "filtro_combustible": "Filtro de combustible / separador",
    "filtro_agua": "Filtro de agua",
    "filtro_aire": "Filtro de aire",
}


@dataclass(frozen=True)
class OpcionesFormulario:
    """Listas que el controlador entrega para llenar combos y sugerencias."""

    marcas: list[str]
    opciones_fases: list[tuple[str, int | None]]
    opciones_combustible: list[tuple[str, str | None]]
    opciones_aceite: list[tuple[str, str | None]]
    voltajes: list[str]
    # Referencias de filtros ya registradas, por campo, para sugerirlas al escribir.
    sugerencias_filtros: dict[str, list[str]] = field(default_factory=dict)


def _marcar_error(widget: QWidget, con_error: bool) -> None:
    """Activa la propiedad "error" que la hoja de estilos pinta con borde rojo."""
    widget.setProperty("error", con_error)
    widget.style().unpolish(widget)  # Obliga a Qt a reaplicar el estilo
    widget.style().polish(widget)


class PlantaFormDialog(QDialog):
    """Formulario modal para registrar o editar los datos técnicos de una planta."""

    guardar_solicitado = Signal(object)  # dict[str, Any]

    def __init__(
        self,
        titulo: str,
        texto_consecutivo: str,
        texto_estado: str,
        opciones: OpcionesFormulario,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setModal(True)

        # campo -> (widget que recibe el borde rojo, etiqueta del mensaje de error)
        self._campos: dict[str, tuple[QWidget, QLabel]] = {}

        self._crear_controles(opciones)
        self._construir_interfaz(titulo, texto_consecutivo, texto_estado)

    # ------------------------------------------------------------------ #
    # Construcción
    # ------------------------------------------------------------------ #

    def _crear_controles(self, opciones: OpcionesFormulario) -> None:
        # Marca: combo editable que sugiere marcas existentes (evita "Cummins" vs "cummins").
        self._marca = QComboBox()
        self._marca.setEditable(True)
        self._marca.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._marca.addItems(opciones.marcas)
        self._marca.setCurrentIndex(-1)
        self._marca.lineEdit().setPlaceholderText("Ej. Cummins")
        completador = self._marca.completer()
        completador.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completador.setFilterMode(Qt.MatchFlag.MatchContains)

        self._modelo = QLineEdit()
        self._numero_serie = QLineEdit()

        # Numéricos: vacíos = "sin dato". Aceptan coma o punto decimal.
        self._potencia_kva = CampoNumerico(decimales=2, placeholder="Ej. 100")
        self._potencia_kw = CampoNumerico(decimales=2, placeholder="Opcional")
        self._capacidad_tanque = CampoNumerico(decimales=2, placeholder="Opcional")
        self._horometro = CampoNumerico(decimales=0, placeholder="Ej. 1.200")
        self._valor_compra = CampoNumerico(
            decimales=0, max_digitos=15, placeholder="Ej. 85.000.000"
        )
        self._cantidad_aceite = CampoNumerico(decimales=2, placeholder="Ej. 2,5")

        self._voltaje = QComboBox()
        self._voltaje.setEditable(True)
        self._voltaje.addItems(opciones.voltajes)
        self._voltaje.setCurrentIndex(-1)
        self._voltaje.lineEdit().setPlaceholderText("Ej. 110/220 V")

        self._fases = self._combo(opciones.opciones_fases)
        self._combustible = self._combo(opciones.opciones_combustible)
        self._tipo_aceite = self._combo(opciones.opciones_aceite)

        # Filtros: texto libre con sugerencias de referencias ya registradas.
        self._filtros: dict[str, QLineEdit] = {}
        for nombre in CAMPOS_FILTROS:
            campo = QLineEdit()
            campo.setPlaceholderText("Referencia, ej. Fleetguard LF3000")
            sugerencias = opciones.sugerencias_filtros.get(nombre, [])
            if sugerencias:
                completador_filtro = QCompleter(sugerencias, campo)
                completador_filtro.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
                completador_filtro.setFilterMode(Qt.MatchFlag.MatchContains)
                campo.setCompleter(completador_filtro)
            self._filtros[nombre] = campo

        # Fecha: QDateEdit no admite "vacío", por eso se acompaña de una casilla.
        self._fecha_conocida = QCheckBox("Registrar fecha")
        self._fecha = QDateEdit()
        self._fecha.setCalendarPopup(True)
        self._fecha.setDisplayFormat("dd/MM/yyyy")
        self._fecha.setMaximumDate(QDate.currentDate())
        self._fecha.setDate(QDate.currentDate())
        self._fecha.setEnabled(False)
        self._fecha_conocida.toggled.connect(self._fecha.setEnabled)

        self._observaciones = QPlainTextEdit()
        self._observaciones.setFixedHeight(64)

    @staticmethod
    def _combo(opciones: list[tuple[str, Any]]) -> QComboBox:
        combo = QComboBox()
        for texto, clave in opciones:
            combo.addItem(texto, clave)
        return combo

    def _construir_interfaz(
        self, titulo: str, texto_consecutivo: str, texto_estado: str
    ) -> None:
        encabezado = QLabel(titulo)
        encabezado.setObjectName("tituloVista")

        self._mensaje_general = QLabel()
        self._mensaje_general.setObjectName("mensajeError")
        self._mensaje_general.setWordWrap(True)
        self._mensaje_general.hide()

        # Grupo 1: información general
        general = QFormLayout()
        general.addRow("Marca *", self._campo("marca", self._marca))
        general.addRow("Modelo", self._campo("modelo", self._modelo))
        general.addRow("Serial", self._campo("numero_serie", self._numero_serie))
        general.addRow("N° Consecutivo", self._etiqueta_informativa(texto_consecutivo))
        general.addRow("Estado", self._etiqueta_informativa(texto_estado))
        caja_general = QGroupBox("Información general")
        caja_general.setLayout(general)

        # Grupo 2: especificaciones técnicas
        tecnico = QFormLayout()
        tecnico.addRow("Potencia (kVA) *", self._campo("potencia_kva", self._potencia_kva))
        tecnico.addRow("Potencia (kW)", self._campo("potencia_kw", self._potencia_kw))
        tecnico.addRow("Voltaje", self._campo("voltaje", self._voltaje))
        tecnico.addRow("Fases", self._campo("fases", self._fases))
        tecnico.addRow("Tipo de combustible", self._campo("tipo_combustible", self._combustible))
        tecnico.addRow(
            "Tanque (galones)", self._campo("capacidad_tanque_gal", self._capacidad_tanque)
        )
        caja_tecnica = QGroupBox("Especificaciones técnicas")
        caja_tecnica.setLayout(tecnico)

        # Grupo 3: adquisición y operación
        fila_fecha = QWidget()
        fila_fecha.setObjectName("envolturaCampo")
        layout_fecha = QHBoxLayout(fila_fecha)
        layout_fecha.setContentsMargins(0, 0, 0, 0)
        layout_fecha.addWidget(self._fecha_conocida)
        layout_fecha.addWidget(self._fecha, stretch=1)

        adquisicion = QFormLayout()
        adquisicion.addRow(
            "Fecha de adquisición", self._campo("fecha_adquisicion", fila_fecha, self._fecha)
        )
        adquisicion.addRow("Valor de compra ($)", self._campo("valor_compra", self._valor_compra))
        adquisicion.addRow(
            "Horómetro inicial (h)", self._campo("horometro_inicial", self._horometro)
        )
        adquisicion.addRow("Observaciones", self._campo("observaciones", self._observaciones))
        caja_adquisicion = QGroupBox("Adquisición y operación")
        caja_adquisicion.setLayout(adquisicion)

        # Grupo 4: consumibles de mantenimiento (pedido en la validación del MVP 1)
        mantenimiento = QFormLayout()
        for nombre, etiqueta in CAMPOS_FILTROS.items():
            mantenimiento.addRow(etiqueta, self._campo(nombre, self._filtros[nombre]))
        mantenimiento.addRow(
            "Cantidad de aceite (gal)", self._campo("cantidad_aceite_gal", self._cantidad_aceite)
        )
        mantenimiento.addRow("Tipo de aceite", self._campo("tipo_aceite", self._tipo_aceite))
        caja_mantenimiento = QGroupBox("Mantenimiento: filtros y aceite")
        caja_mantenimiento.setLayout(mantenimiento)

        # Botones
        boton_guardar = QPushButton("Guardar")
        boton_guardar.setObjectName("botonPrimario")
        boton_guardar.setDefault(True)
        boton_guardar.clicked.connect(self._al_guardar)
        boton_cancelar = QPushButton("Cancelar")
        boton_cancelar.clicked.connect(self.reject)
        botones = QHBoxLayout()
        nota = QLabel("* Campos obligatorios")
        nota.setObjectName("textoSecundario")
        botones.addWidget(nota)
        botones.addStretch()
        botones.addWidget(boton_cancelar)
        botones.addWidget(boton_guardar)

        # Cuadrícula de 2 x 2 grupos, como la ficha técnica del wireframe.
        grupos = QGridLayout()
        grupos.addWidget(caja_general, 0, 0)
        grupos.addWidget(caja_tecnica, 0, 1)
        grupos.addWidget(caja_adquisicion, 1, 0)
        grupos.addWidget(caja_mantenimiento, 1, 1)
        grupos.setColumnStretch(0, 1)
        grupos.setColumnStretch(1, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(encabezado)
        layout.addWidget(self._mensaje_general)
        layout.addLayout(grupos)
        layout.addLayout(botones)
        # El diálogo se ajusta solo a su contenido: al aparecer mensajes de error
        # crece lo necesario para mostrarlos completos, sin recortarlos.
        layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

    def _campo(self, nombre: str, contenedor: QWidget, resaltar: QWidget | None = None) -> QWidget:
        """
        Envuelve un control con su etiqueta de error (oculta hasta que haga falta).

        Args:
            nombre: Nombre del campo en DatosPlanta.
            contenedor: Lo que se ubica en el formulario.
            resaltar: Control que recibe el borde rojo (por defecto, el contenedor).
        """
        etiqueta_error = QLabel()
        etiqueta_error.setObjectName("errorCampo")
        etiqueta_error.setWordWrap(True)
        etiqueta_error.hide()

        envoltura = QWidget()
        envoltura.setObjectName("envolturaCampo")  # Fondo transparente en el QSS
        layout = QVBoxLayout(envoltura)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(contenedor)
        layout.addWidget(etiqueta_error)

        self._campos[nombre] = (resaltar or contenedor, etiqueta_error)
        return envoltura

    @staticmethod
    def _etiqueta_informativa(texto: str) -> QLabel:
        etiqueta = QLabel(texto)
        etiqueta.setObjectName("datoSistema")
        etiqueta.setToolTip("Lo asigna el sistema; no se edita en este formulario.")
        return etiqueta

    # ------------------------------------------------------------------ #
    # Eventos
    # ------------------------------------------------------------------ #

    def _al_guardar(self) -> None:
        self.limpiar_errores()
        self.guardar_solicitado.emit(self.valores())

    # ------------------------------------------------------------------ #
    # API pública
    # ------------------------------------------------------------------ #

    def valores(self) -> dict[str, Any]:
        """Lee el formulario y devuelve los valores con sus tipos de Python."""
        valores: dict[str, Any] = {
            "marca": self._marca.currentText(),
            "modelo": self._modelo.text(),
            "numero_serie": self._numero_serie.text(),
            "potencia_kva": self._potencia_kva.valor(),
            "potencia_kw": self._potencia_kw.valor(),
            "voltaje": self._voltaje.currentText(),
            "fases": self._fases.currentData(),
            "tipo_combustible": self._combustible.currentData(),
            "capacidad_tanque_gal": self._capacidad_tanque.valor(),
            "fecha_adquisicion": (
                self._fecha.date().toPython() if self._fecha_conocida.isChecked() else None
            ),
            "valor_compra": self._valor_compra.valor_entero(),
            "horometro_inicial": self._horometro.valor_entero(),
            "observaciones": self._observaciones.toPlainText(),
            "cantidad_aceite_gal": self._cantidad_aceite.valor(),
            "tipo_aceite": self._tipo_aceite.currentData(),
        }
        for nombre, campo in self._filtros.items():
            valores[nombre] = campo.text()
        return valores

    def cargar_valores(self, valores: dict[str, Any]) -> None:
        """Llena el formulario con los datos de una planta existente (modo edición)."""
        self._marca.setCurrentText(valores.get("marca") or "")
        self._modelo.setText(valores.get("modelo") or "")
        self._numero_serie.setText(valores.get("numero_serie") or "")
        self._potencia_kva.set_valor(valores.get("potencia_kva"))
        self._potencia_kw.set_valor(valores.get("potencia_kw"))
        self._voltaje.setCurrentText(valores.get("voltaje") or "")
        self._seleccionar(self._fases, valores.get("fases"))
        self._seleccionar(self._combustible, valores.get("tipo_combustible"))
        self._capacidad_tanque.set_valor(valores.get("capacidad_tanque_gal"))

        fecha: date | None = valores.get("fecha_adquisicion")
        self._fecha_conocida.setChecked(fecha is not None)
        if fecha is not None:
            self._fecha.setDate(QDate(fecha.year, fecha.month, fecha.day))

        self._valor_compra.set_valor(valores.get("valor_compra"))
        self._horometro.set_valor(valores.get("horometro_inicial"))
        self._observaciones.setPlainText(valores.get("observaciones") or "")
        for nombre, campo in self._filtros.items():
            campo.setText(valores.get(nombre) or "")
        self._cantidad_aceite.set_valor(valores.get("cantidad_aceite_gal"))
        self._seleccionar(self._tipo_aceite, valores.get("tipo_aceite"))

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
            _marcar_error(control, True)
            primero = primero or control

        self._mensaje_general.setText(
            " ".join(["Revise los campos marcados en rojo.", *sin_campo])
        )
        self._mensaje_general.show()
        if primero is not None:
            primero.setFocus()

    def limpiar_errores(self) -> None:
        self._mensaje_general.hide()
        for control, etiqueta in self._campos.values():
            etiqueta.hide()
            _marcar_error(control, False)

    def mostrar_error(self, mensaje: str) -> None:
        QMessageBox.warning(self, self.windowTitle(), mensaje)

    # ------------------------------------------------------------------ #
    # Auxiliares
    # ------------------------------------------------------------------ #

    @staticmethod
    def _seleccionar(combo: QComboBox, clave: object) -> None:
        indice = combo.findData(clave)
        combo.setCurrentIndex(max(indice, 0))
