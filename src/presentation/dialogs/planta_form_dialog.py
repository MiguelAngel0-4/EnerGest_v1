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
"""

import re
from datetime import date
from typing import Any, Final

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
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
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

_SIN_DATO: Final[str] = "—"


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
        marcas: list[str],
        opciones_fases: list[tuple[str, int | None]],
        opciones_combustible: list[tuple[str, str | None]],
        voltajes: list[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setModal(True)

        # campo -> (widget que recibe el borde rojo, etiqueta del mensaje de error)
        self._campos: dict[str, tuple[QWidget, QLabel]] = {}

        self._crear_controles(marcas, opciones_fases, opciones_combustible, voltajes)
        self._construir_interfaz(titulo, texto_consecutivo, texto_estado)

    # ------------------------------------------------------------------ #
    # Construcción
    # ------------------------------------------------------------------ #

    def _crear_controles(
        self,
        marcas: list[str],
        opciones_fases: list[tuple[str, int | None]],
        opciones_combustible: list[tuple[str, str | None]],
        voltajes: list[str],
    ) -> None:
        # Marca: combo editable que sugiere marcas existentes (evita "Cummins" vs "cummins").
        self._marca = QComboBox()
        self._marca.setEditable(True)
        self._marca.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._marca.addItems(marcas)
        self._marca.setCurrentIndex(-1)
        self._marca.lineEdit().setPlaceholderText("Ej. Cummins")
        completador = self._marca.completer()
        completador.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completador.setFilterMode(Qt.MatchFlag.MatchContains)

        self._modelo = QLineEdit()
        self._numero_serie = QLineEdit()

        self._potencia_kva = self._spin_decimal(100_000, " kVA", opcional=False)
        self._potencia_kw = self._spin_decimal(100_000, " kW", opcional=True)
        self._capacidad_tanque = self._spin_decimal(100_000, " gal", opcional=True)

        self._voltaje = QComboBox()
        self._voltaje.setEditable(True)
        self._voltaje.addItems(voltajes)
        self._voltaje.setCurrentIndex(-1)
        self._voltaje.lineEdit().setPlaceholderText("Ej. 120/240 V")

        self._fases = QComboBox()
        for texto, clave in opciones_fases:
            self._fases.addItem(texto, clave)

        self._combustible = QComboBox()
        for texto, clave in opciones_combustible:
            self._combustible.addItem(texto, clave)

        # Fecha: QDateEdit no admite "vacío", por eso se acompaña de una casilla.
        self._fecha_conocida = QCheckBox("Registrar fecha")
        self._fecha = QDateEdit()
        self._fecha.setCalendarPopup(True)
        self._fecha.setDisplayFormat("dd/MM/yyyy")
        self._fecha.setMaximumDate(QDate.currentDate())
        self._fecha.setDate(QDate.currentDate())
        self._fecha.setEnabled(False)
        self._fecha_conocida.toggled.connect(self._fecha.setEnabled)

        # Valor de compra: texto (QSpinBox solo llega a 2.147.483.647).
        self._valor_compra = QLineEdit()
        self._valor_compra.setPlaceholderText("Ej. 85.000.000")
        self._valor_compra.setValidator(
            QRegularExpressionValidator(r"[0-9.]{0,19}", self._valor_compra)
        )
        self._valor_compra.editingFinished.connect(self._formatear_valor_compra)

        self._horometro = QSpinBox()
        self._horometro.setRange(0, 9_999_999)
        self._horometro.setSuffix(" h")
        self._horometro.setGroupSeparatorShown(True)
        self._horometro.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        self._observaciones = QPlainTextEdit()
        self._observaciones.setFixedHeight(64)

    @staticmethod
    def _spin_decimal(maximo: float, sufijo: str, opcional: bool) -> QDoubleSpinBox:
        """Campo numérico decimal. Si es opcional, el valor 0 se muestra como "—" (sin dato)."""
        spin = QDoubleSpinBox()
        spin.setRange(0, maximo)
        spin.setDecimals(2)
        spin.setSuffix(sufijo)
        spin.setGroupSeparatorShown(True)
        spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        if opcional:
            spin.setSpecialValueText(_SIN_DATO)
        return spin

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
            "Capacidad del tanque", self._campo("capacidad_tanque_gal", self._capacidad_tanque)
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

        adquisicion = QGridLayout()
        adquisicion.addWidget(QLabel("Fecha de adquisición"), 0, 0)
        adquisicion.addWidget(self._campo("fecha_adquisicion", fila_fecha, self._fecha), 0, 1)
        adquisicion.addWidget(QLabel("Valor de compra ($)"), 0, 2)
        adquisicion.addWidget(self._campo("valor_compra", self._valor_compra), 0, 3)
        adquisicion.addWidget(QLabel("Horómetro inicial"), 1, 0)
        adquisicion.addWidget(self._campo("horometro_inicial", self._horometro), 1, 1)
        adquisicion.addWidget(QLabel("Observaciones"), 2, 0, Qt.AlignmentFlag.AlignTop)
        adquisicion.addWidget(self._campo("observaciones", self._observaciones), 2, 1, 1, 3)
        adquisicion.setColumnStretch(1, 1)
        adquisicion.setColumnStretch(3, 1)
        caja_adquisicion = QGroupBox("Adquisición y operación")
        caja_adquisicion.setLayout(adquisicion)

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

        columnas = QHBoxLayout()
        columnas.addWidget(caja_general, stretch=1)
        columnas.addWidget(caja_tecnica, stretch=1)

        layout = QVBoxLayout(self)
        layout.addWidget(encabezado)
        layout.addWidget(self._mensaje_general)
        layout.addLayout(columnas)
        layout.addWidget(caja_adquisicion)
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

    def _formatear_valor_compra(self) -> None:
        """Muestra el valor con separador de miles al salir del campo: 85000000 -> 85.000.000."""
        digitos = re.sub(r"\D", "", self._valor_compra.text())
        self._valor_compra.setText(f"{int(digitos):,}".replace(",", ".") if digitos else "")

    # ------------------------------------------------------------------ #
    # API pública
    # ------------------------------------------------------------------ #

    def valores(self) -> dict[str, Any]:
        """Lee el formulario y devuelve los valores con sus tipos de Python."""
        digitos_valor = re.sub(r"\D", "", self._valor_compra.text())
        return {
            "marca": self._marca.currentText(),
            "modelo": self._modelo.text(),
            "numero_serie": self._numero_serie.text(),
            "potencia_kva": self._potencia_kva.value(),
            "potencia_kw": self._valor_opcional(self._potencia_kw),
            "voltaje": self._voltaje.currentText(),
            "fases": self._fases.currentData(),
            "tipo_combustible": self._combustible.currentData(),
            "capacidad_tanque_gal": self._valor_opcional(self._capacidad_tanque),
            "fecha_adquisicion": (
                self._fecha.date().toPython() if self._fecha_conocida.isChecked() else None
            ),
            "valor_compra": int(digitos_valor) if digitos_valor else None,
            "horometro_inicial": self._horometro.value(),
            "observaciones": self._observaciones.toPlainText(),
        }

    def cargar_valores(self, valores: dict[str, Any]) -> None:
        """Llena el formulario con los datos de una planta existente (modo edición)."""
        self._marca.setCurrentText(valores.get("marca") or "")
        self._modelo.setText(valores.get("modelo") or "")
        self._numero_serie.setText(valores.get("numero_serie") or "")
        self._potencia_kva.setValue(valores.get("potencia_kva") or 0)
        self._potencia_kw.setValue(valores.get("potencia_kw") or 0)
        self._voltaje.setCurrentText(valores.get("voltaje") or "")
        self._seleccionar(self._fases, valores.get("fases"))
        self._seleccionar(self._combustible, valores.get("tipo_combustible"))
        self._capacidad_tanque.setValue(valores.get("capacidad_tanque_gal") or 0)

        fecha: date | None = valores.get("fecha_adquisicion")
        self._fecha_conocida.setChecked(fecha is not None)
        if fecha is not None:
            self._fecha.setDate(QDate(fecha.year, fecha.month, fecha.day))

        valor = valores.get("valor_compra")
        self._valor_compra.setText(f"{valor:,}".replace(",", ".") if valor is not None else "")
        self._horometro.setValue(valores.get("horometro_inicial") or 0)
        self._observaciones.setPlainText(valores.get("observaciones") or "")

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
    def _valor_opcional(spin: QDoubleSpinBox) -> float | None:
        """El mínimo (que se muestra como "—") significa "sin dato"."""
        return None if spin.value() == spin.minimum() else spin.value()

    @staticmethod
    def _seleccionar(combo: QComboBox, clave: object) -> None:
        indice = combo.findData(clave)
        combo.setCurrentIndex(max(indice, 0))
