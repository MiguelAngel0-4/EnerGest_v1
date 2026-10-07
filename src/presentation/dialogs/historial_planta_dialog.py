"""
Diálogo de historial de una planta.

Ruta: src/presentation/dialogs/historial_planta_dialog.py

Dos pestañas de solo lectura: la línea de tiempo de estados y los
números consecutivos que ha tenido la planta. Recibe los textos ya
formateados por el controlador, así que no conoce los modelos de negocio.
"""

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

FilaTexto = tuple[str, ...]


class HistorialPlantaDialog(QDialog):
    """Muestra la trazabilidad completa de una planta."""

    def __init__(
        self,
        descripcion_planta: str,
        filas_estados: list[FilaTexto],
        filas_consecutivos: list[FilaTexto],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Historial de la planta")
        self.setModal(True)
        self.resize(760, 420)

        titulo = QLabel(f"Historial – {descripcion_planta}")
        titulo.setObjectName("tituloPanel")

        pestanas = QTabWidget()
        pestanas.addTab(
            self._tabla(
                ["Fecha", "Estado anterior", "Estado nuevo", "Horómetro", "Motivo"], filas_estados
            ),
            f"Estados ({len(filas_estados)})",
        )
        pestanas.addTab(
            self._tabla(["Número", "Asignado", "Liberado", "Motivo"], filas_consecutivos),
            f"Números consecutivos ({len(filas_consecutivos)})",
        )

        boton_cerrar = QPushButton("Cerrar")
        boton_cerrar.setDefault(True)
        boton_cerrar.clicked.connect(self.accept)
        botones = QHBoxLayout()
        botones.addStretch()
        botones.addWidget(boton_cerrar)

        layout = QVBoxLayout(self)
        layout.addWidget(titulo)
        layout.addWidget(pestanas, stretch=1)
        layout.addLayout(botones)

    @staticmethod
    def _tabla(encabezados: list[str], filas: list[FilaTexto]) -> QTableWidget:
        """Tabla simple de solo lectura; la última columna (motivo) ocupa el espacio libre."""
        tabla = QTableWidget(len(filas), len(encabezados))
        tabla.setHorizontalHeaderLabels(encabezados)
        tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tabla.setAlternatingRowColors(True)
        tabla.verticalHeader().setVisible(False)
        for i, fila in enumerate(filas):
            for j, texto in enumerate(fila):
                tabla.setItem(i, j, QTableWidgetItem(texto))
        encabezado = tabla.horizontalHeader()
        encabezado.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        encabezado.setSectionResizeMode(len(encabezados) - 1, QHeaderView.ResizeMode.Stretch)
        return tabla
