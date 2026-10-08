"""
Tabla simple de solo lectura a partir de filas de texto.

Ruta: src/presentation/widgets/tabla_texto.py
"""

from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem

FilaTexto = tuple[str, ...]


def crear_tabla_texto(encabezados: list[str], filas: list[FilaTexto]) -> QTableWidget:
    """La última columna (normalmente "Motivo" o "Descripción") ocupa el espacio libre."""
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
