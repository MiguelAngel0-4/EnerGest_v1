"""
Vista del inventario general de plantas.

Ruta: src/presentation/views/equipos/inventario_view.py

Patrón Vista Pasiva: esta clase es el "mesero". Muestra información y
avisa lo que el usuario pidió mediante SEÑALES, pero no decide nada ni
conoce los servicios. Por eso no importa nada de business ni infrastructure.
"""

from typing import Final

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStyledItemDelegate,
    QTableView,
    QVBoxLayout,
    QWidget,
)

_ESPERA_BUSQUEDA_MS: Final[int] = 300  # Espera a que el usuario deje de escribir


class InventarioView(QWidget):
    """Pantalla de control de inventario (Panel B del wireframe)."""

    # --- Señales: "lo que el usuario pidió" -----------------------------------
    busqueda_cambiada = Signal(str)
    filtros_cambiados = Signal()
    registro_solicitado = Signal()
    fila_activada = Signal(QModelIndex)
    numero_consultado = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._temporizador_busqueda = QTimer(self)
        self._temporizador_busqueda.setSingleShot(True)
        self._temporizador_busqueda.setInterval(_ESPERA_BUSQUEDA_MS)
        self._construir_interfaz()
        self._conectar_eventos()

    # ------------------------------------------------------------------ #
    # Construcción
    # ------------------------------------------------------------------ #

    def _construir_interfaz(self) -> None:
        # Encabezado: título + botón principal
        self._titulo = QLabel("Control de Inventario General")
        self._titulo.setObjectName("tituloVista")
        self._boton_registrar = QPushButton("Registrar nueva planta")
        self._boton_registrar.setObjectName("botonPrimario")
        self._boton_registrar.setCursor(Qt.CursorShape.PointingHandCursor)

        encabezado = QHBoxLayout()
        encabezado.addWidget(self._titulo)
        encabezado.addStretch()
        encabezado.addWidget(self._boton_registrar)

        # Barra de filtros
        self._busqueda = QLineEdit()
        self._busqueda.setPlaceholderText("Buscar por marca, modelo o serial…")
        self._busqueda.setClearButtonEnabled(True)
        self._combo_marca = QComboBox()
        self._combo_potencia = QComboBox()
        self._combo_estado = QComboBox()
        for combo in (self._combo_marca, self._combo_potencia, self._combo_estado):
            combo.setMinimumWidth(150)

        filtros = QHBoxLayout()
        filtros.addWidget(self._busqueda, stretch=2)
        filtros.addWidget(self._combo_marca, stretch=1)
        filtros.addWidget(self._combo_potencia, stretch=1)
        filtros.addWidget(self._combo_estado, stretch=1)

        # Tabla
        self._tabla = QTableView()
        self._tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tabla.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tabla.setAlternatingRowColors(True)
        self._tabla.setSortingEnabled(True)
        self._tabla.verticalHeader().setVisible(False)
        self._tabla.verticalHeader().setDefaultSectionSize(36)
        self._tabla.setMouseTracking(True)

        self._resumen = QLabel()
        self._resumen.setObjectName("textoSecundario")

        columna_principal = QVBoxLayout()
        columna_principal.addLayout(encabezado)
        columna_principal.addLayout(filtros)
        columna_principal.addWidget(self._tabla, stretch=1)
        columna_principal.addWidget(self._resumen)

        # Panel derecho: números libres (informativo)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(16)
        layout.addLayout(columna_principal, stretch=1)
        layout.addWidget(self._construir_panel_numeros())

    def _construir_panel_numeros(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panelNumeros")
        panel.setFixedWidth(220)

        titulo = QLabel("Números disponibles")
        titulo.setObjectName("tituloPanel")

        self._lista_numeros = QListWidget()
        self._lista_numeros.setCursor(Qt.CursorShape.PointingHandCursor)
        self._lista_numeros.setToolTip("Haga clic en un número para ver qué plantas lo han tenido.")

        self._proximo = QLabel()
        self._proximo.setObjectName("proximoNumero")
        self._proximo.setWordWrap(True)

        nota = QLabel(
            "Asignación automática: cada planta nueva recibe el menor número libre."
        )
        nota.setObjectName("textoSecundario")
        nota.setWordWrap(True)

        layout = QVBoxLayout(panel)
        layout.addWidget(titulo)
        layout.addWidget(self._lista_numeros, stretch=1)
        layout.addWidget(self._proximo)
        layout.addWidget(nota)
        return panel

    def _conectar_eventos(self) -> None:
        self._boton_registrar.clicked.connect(self.registro_solicitado)
        # La búsqueda espera 300 ms sin teclear antes de avisar (evita consultas por cada letra).
        self._busqueda.textChanged.connect(lambda _texto: self._temporizador_busqueda.start())
        self._temporizador_busqueda.timeout.connect(
            lambda: self.busqueda_cambiada.emit(self._busqueda.text())
        )
        for combo in (self._combo_marca, self._combo_potencia, self._combo_estado):
            combo.currentIndexChanged.connect(lambda _i: self.filtros_cambiados.emit())
        self._tabla.doubleClicked.connect(self.fila_activada)
        self._lista_numeros.itemClicked.connect(self._al_hacer_clic_en_numero)

    def _al_hacer_clic_en_numero(self, item: QListWidgetItem) -> None:
        numero = item.data(Qt.ItemDataRole.UserRole)
        if numero is not None:
            self.numero_consultado.emit(int(numero))

    # ------------------------------------------------------------------ #
    # API pública: lo que el controlador le pide a la vista
    # ------------------------------------------------------------------ #

    def set_modelo(
        self,
        modelo: QAbstractItemModel,
        anchos_fijos: dict[int, int],
        columnas_flexibles: list[int],
    ) -> None:
        """
        Conecta el modelo de datos y distribuye el ancho de las columnas.

        Args:
            anchos_fijos: {columna: píxeles} para datos de largo predecible.
            columnas_flexibles: Columnas que se reparten el espacio sobrante.
        """
        self._tabla.setModel(modelo)
        encabezado = self._tabla.horizontalHeader()
        encabezado.setMinimumSectionSize(60)
        for columna, ancho in anchos_fijos.items():
            encabezado.setSectionResizeMode(columna, QHeaderView.ResizeMode.Fixed)
            self._tabla.setColumnWidth(columna, ancho)
        for columna in columnas_flexibles:
            encabezado.setSectionResizeMode(columna, QHeaderView.ResizeMode.Stretch)
        encabezado.setSortIndicatorClearable(True)
        self._tabla.sortByColumn(0, Qt.SortOrder.AscendingOrder)

    def set_delegado_acciones(self, delegado: QStyledItemDelegate, columna: int) -> None:
        """Asigna el pintor de botones a la columna de acciones."""
        self._tabla.setItemDelegateForColumn(columna, delegado)

    def set_opciones_combo(
        self, nombre: str, opciones: list[tuple[str, str | None]], conservar: bool = True
    ) -> None:
        """
        Llena un combo de filtro con (texto visible, clave interna).

        Args:
            nombre: "marca", "potencia" o "estado".
            conservar: Mantener la selección actual si sigue existiendo.
        """
        combo = self._combo(nombre)
        clave_actual = combo.currentData() if conservar else None
        combo.blockSignals(True)  # Llenar el combo no debe disparar filtros
        combo.clear()
        for texto, clave in opciones:
            combo.addItem(texto, clave)
        indice = combo.findData(clave_actual) if clave_actual is not None else 0
        combo.setCurrentIndex(max(indice, 0))
        combo.blockSignals(False)

    def valor_filtro(self, nombre: str) -> str | None:
        """Clave interna seleccionada en un combo de filtro."""
        return self._combo(nombre).currentData()

    def texto_busqueda(self) -> str:
        return self._busqueda.text()

    def mostrar_numeros_libres(self, numeros: list[tuple[str, int]], proximo: str) -> None:
        """Muestra los números libres como (texto visible, número)."""
        self._lista_numeros.clear()
        for texto, numero in numeros:
            item = QListWidgetItem(texto)
            item.setData(Qt.ItemDataRole.UserRole, numero)
            self._lista_numeros.addItem(item)
        if not numeros:
            vacio = QListWidgetItem("No hay números liberados")
            vacio.setFlags(Qt.ItemFlag.NoItemFlags)
            self._lista_numeros.addItem(vacio)
        self._proximo.setText(f"Próximo número a asignar: <b>{proximo}</b>")

    def mostrar_resumen(self, texto: str) -> None:
        self._resumen.setText(texto)

    def mostrar_error(self, titulo: str, mensaje: str) -> None:
        QMessageBox.warning(self, titulo, mensaje)

    def mostrar_info(self, titulo: str, mensaje: str) -> None:
        QMessageBox.information(self, titulo, mensaje)

    def _combo(self, nombre: str) -> QComboBox:
        combos = {
            "marca": self._combo_marca,
            "potencia": self._combo_potencia,
            "estado": self._combo_estado,
        }
        return combos[nombre]
