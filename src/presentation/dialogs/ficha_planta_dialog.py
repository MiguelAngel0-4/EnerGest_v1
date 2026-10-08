"""
Ficha de una planta: ventana con pestañas (Propuesta 2 del wireframe).

Ruta: src/presentation/dialogs/ficha_planta_dialog.py

Reúne todo lo que se sabe de una planta. Cada sub-iteración de la
Actividad 4 habilita una pestaña nueva, sin tocar el inventario.
"""

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.presentation.widgets.gastos_widget import GastosWidget
from src.presentation.widgets.ingresos_widget import IngresosWidget
from src.presentation.widgets.mantenimientos_widget import MantenimientosWidget
from src.presentation.widgets.tabla_texto import FilaTexto, crear_tabla_texto

_PROXIMAMENTE = ("Balance",)


class FichaPlantaDialog(QDialog):
    """Ventana de detalle de una planta."""

    def __init__(
        self,
        descripcion_planta: str,
        filas_estados: list[FilaTexto],
        filas_consecutivos: list[FilaTexto],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ficha de la planta")
        self.setModal(True)
        self.resize(1000, 620)

        titulo = QLabel(f"Ficha – {descripcion_planta}")
        titulo.setObjectName("tituloVista")

        self._pestanas = QTabWidget()
        self._pestanas.addTab(self._historial(filas_estados, filas_consecutivos), "Historial")
        self.gastos = GastosWidget()
        self._pestanas.addTab(self.gastos, "Gastos")
        self.mantenimientos = MantenimientosWidget()
        self._pestanas.addTab(self.mantenimientos, "Mantenimientos")
        self.ingresos = IngresosWidget()
        self._pestanas.addTab(self.ingresos, "Ingresos")
        for nombre in _PROXIMAMENTE:
            indice = self._pestanas.addTab(QWidget(), nombre)
            self._pestanas.setTabEnabled(indice, False)
            self._pestanas.setTabToolTip(indice, "Disponible en próximas versiones")

        boton_cerrar = QPushButton("Cerrar")
        boton_cerrar.clicked.connect(self.accept)
        botones = QHBoxLayout()
        botones.addStretch()
        botones.addWidget(boton_cerrar)

        layout = QVBoxLayout(self)
        layout.addWidget(titulo)
        layout.addWidget(self._pestanas, stretch=1)
        layout.addLayout(botones)

    def mostrar_pestana(self, nombre: str) -> None:
        for indice in range(self._pestanas.count()):
            if self._pestanas.tabText(indice) == nombre:
                self._pestanas.setCurrentIndex(indice)
                return

    @staticmethod
    def _historial(estados: list[FilaTexto], consecutivos: list[FilaTexto]) -> QWidget:
        contenedor = QWidget()
        layout = QVBoxLayout(contenedor)
        titulo_estados = QLabel(f"Cambios de estado ({len(estados)})")
        titulo_estados.setObjectName("tituloPanel")
        titulo_numeros = QLabel(f"Números consecutivos ({len(consecutivos)})")
        titulo_numeros.setObjectName("tituloPanel")
        layout.addWidget(titulo_estados)
        layout.addWidget(
            crear_tabla_texto(
                ["Fecha", "Estado anterior", "Estado nuevo", "Horómetro", "Motivo"], estados
            ),
            stretch=2,
        )
        layout.addWidget(titulo_numeros)
        layout.addWidget(
            crear_tabla_texto(["Número", "Asignado", "Liberado", "Motivo"], consecutivos),
            stretch=1,
        )
        return contenedor
