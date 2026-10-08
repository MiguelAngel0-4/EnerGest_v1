"""
Pestaña "Gastos" de la ficha de una planta.

Ruta: src/presentation/widgets/gastos_widget.py

Usa la base común RegistrosWidget; solo define sus columnas.
"""

from typing import NamedTuple

from PySide6.QtWidgets import QWidget

from src.presentation.widgets.registros_widget import FilaRegistro, RegistrosWidget


class FilaGasto(NamedTuple):
    """Una fila de la tabla, con los textos ya formateados por el controlador."""

    id: int
    fecha: str
    categoria: str
    descripcion: str
    cantidad: str
    valor: str
    soporte: str
    anulado: bool = False
    motivo_anulacion: str | None = None


class GastosWidget(RegistrosWidget):
    """Lista de gastos de una planta con sus acciones y totales."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            ["Fecha", "Categoría", "Descripción", "Cantidad", "Valor", "Soporte"],
            "Registrar gasto",
            "Anular gasto",
            columna_estirable=2,
            columnas_a_la_derecha=(3, 4),
            parent=parent,
        )

    def mostrar_gastos(self, filas: list[FilaGasto]) -> None:
        self.mostrar_filas(
            [
                FilaRegistro(
                    f.id,
                    (f.fecha, f.categoria, f.descripcion, f.cantidad, f.valor, f.soporte),
                    f.anulado,
                    f.motivo_anulacion,
                )
                for f in filas
            ]
        )

    def gasto_seleccionado(self) -> int | None:
        return self.registro_seleccionado()
