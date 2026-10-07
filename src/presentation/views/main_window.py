"""
Ventana principal de EnerGest.

Ruta: src/presentation/views/main_window.py

Estructura (Panel A del wireframe):
- Izquierda: menú lateral de navegación.
- Derecha: contenedor de vistas (QStackedWidget). Funciona como las
  páginas de un libro: todas existen, pero solo se muestra una a la vez.
"""

from typing import Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

_TEXTO_PROXIMAMENTE: Final[str] = "Disponible en próximas versiones"


class MainWindow(QMainWindow):
    """Ventana principal: menú lateral + contenedor de vistas + barra de estado."""

    registro_solicitado = Signal()

    def __init__(self, titulo: str, version: str) -> None:
        super().__init__()
        self.setWindowTitle(f"{titulo} – v{version}")
        self.resize(1366, 760)
        self.setMinimumSize(1200, 640)

        self._vistas: dict[str, QWidget] = {}
        self._contenedor = QStackedWidget()
        self._grupo_navegacion = QButtonGroup(self)
        self._grupo_navegacion.setExclusive(True)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._construir_menu_lateral())
        layout.addWidget(self._contenedor, stretch=1)
        self.setCentralWidget(central)

        self._etiqueta_estado = QLabel()
        self._etiqueta_estado.setObjectName("textoSecundario")
        self.statusBar().addPermanentWidget(self._etiqueta_estado)

    def _construir_menu_lateral(self) -> QFrame:
        menu = QFrame()
        menu.setObjectName("menuLateral")
        menu.setFixedWidth(190)

        logo = QLabel("EG")
        logo.setObjectName("logo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitulo = QLabel("EnerGest")
        subtitulo.setObjectName("subtituloLogo")
        subtitulo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._boton_inventario = self._boton_menu("Inventario", navegable=True)
        self._boton_inventario.clicked.connect(lambda: self.mostrar_vista("inventario"))

        boton_registro = self._boton_menu("Registro nuevo")
        boton_registro.clicked.connect(self.registro_solicitado)

        boton_reportes = self._boton_menu("Reportes financieros")
        boton_configuracion = self._boton_menu("Configuración")
        for boton in (boton_reportes, boton_configuracion):
            boton.setEnabled(False)
            boton.setToolTip(_TEXTO_PROXIMAMENTE)

        boton_salir = self._boton_menu("Salir")
        boton_salir.clicked.connect(self.close)

        layout = QVBoxLayout(menu)
        layout.setContentsMargins(12, 20, 12, 16)
        layout.setSpacing(6)
        layout.addWidget(logo)
        layout.addWidget(subtitulo)
        layout.addSpacing(24)
        for boton in (self._boton_inventario, boton_registro, boton_reportes, boton_configuracion):
            layout.addWidget(boton)
        layout.addStretch()
        layout.addWidget(boton_salir)
        return menu

    def _boton_menu(self, texto: str, navegable: bool = False) -> QPushButton:
        """Crea un botón del menú. Los navegables quedan marcados al estar activos."""
        boton = QPushButton(texto)
        boton.setObjectName("botonMenu")
        boton.setCursor(Qt.CursorShape.PointingHandCursor)
        if navegable:
            boton.setCheckable(True)
            self._grupo_navegacion.addButton(boton)
        return boton

    # ------------------------------------------------------------------ #
    # API pública
    # ------------------------------------------------------------------ #

    def agregar_vista(self, clave: str, vista: QWidget) -> None:
        """Registra una vista en el contenedor. La primera se muestra por defecto."""
        self._vistas[clave] = vista
        self._contenedor.addWidget(vista)
        if len(self._vistas) == 1:
            self.mostrar_vista(clave)

    def mostrar_vista(self, clave: str) -> None:
        """Cambia la "página" visible del contenedor."""
        self._contenedor.setCurrentWidget(self._vistas[clave])
        if clave == "inventario":
            self._boton_inventario.setChecked(True)

    def set_mensaje_estado(self, texto: str) -> None:
        """Texto permanente en la barra inferior (versión, ubicación de la BD)."""
        self._etiqueta_estado.setText(texto)
