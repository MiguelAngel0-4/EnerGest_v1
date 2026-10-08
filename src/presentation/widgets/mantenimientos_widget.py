"""
Pestaña "Mantenimientos" de la ficha de una planta.

Ruta: src/presentation/widgets/mantenimientos_widget.py
"""

from PySide6.QtWidgets import QWidget

from src.presentation.widgets.registros_widget import RegistrosWidget

ENCABEZADOS_MANTENIMIENTOS = [
    "Fecha",
    "Tipo",
    "Horómetro",
    "Técnico",
    "Trabajo realizado",
    "Costo",
    "Próximo",
]


class MantenimientosWidget(RegistrosWidget):
    """Lista de mantenimientos de una planta con sus acciones y resumen."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            ENCABEZADOS_MANTENIMIENTOS,
            "Registrar mantenimiento",
            "Anular mantenimiento",
            columna_estirable=4,
            columnas_a_la_derecha=(2, 5),
            parent=parent,
        )
