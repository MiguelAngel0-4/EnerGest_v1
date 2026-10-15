"""
Modelo de la tabla por planta de los Reportes financieros.

Ruta: src/presentation/table_models/reporte_table_model.py

Cada celda tiene dos caras:
- DisplayRole: el texto que se ve ("$ 1.250.000").
- UserRole: el valor real (1250000), que se usa para ORDENAR.

Si se ordenara por el texto, "$ 9.000" quedaría después de "$ 10.000",
porque como palabras "9" va después de "1": el clásico error de ordenar
números como si fueran texto.
"""

from enum import IntEnum
from typing import Any, NamedTuple

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPixmap

from src.shared.colores import SEMAFORO
from src.shared.formatters import formatear_moneda, formatear_porcentaje

_INDICE = QModelIndex | QPersistentModelIndex


class Col(IntEnum):
    NUMERO = 0
    PLANTA = 1
    ESTADO = 2
    INGRESOS = 3
    GASTOS = 4
    RESULTADO = 5
    DESGASTE = 6
    SEMAFORO = 7


ENCABEZADOS = ["N°", "Planta", "Estado", "Ingresos", "Gastos", "Resultado", "Desgaste", "Semáforo"]

# Orden de gravedad del semáforo, para ordenar la columna de lo más grave a lo menos.
_GRAVEDAD = {"EVALUAR_REEMPLAZO": 0, "VIGILAR": 1, "RENTABLE": 2, "SIN_DATOS": 3}


class FilaTablaReporte(NamedTuple):
    planta_id: int
    numero: str  # "PE-004" o "—"
    numero_orden: int  # Para ordenar; las plantas sin número van al final
    planta: str
    estado: str
    ingresos: int
    gastos: int
    resultado: int
    desgaste: float | None
    nivel: str  # Clave de NivelIndicador
    nivel_texto: str
    razones: str


class ReporteTableModel(QAbstractTableModel):
    def __init__(self) -> None:
        super().__init__()
        self._filas: list[FilaTablaReporte] = []
        self._iconos = {nivel: _punto(color) for nivel, (_fondo, color) in SEMAFORO.items()}

    def cargar(self, filas: list[FilaTablaReporte]) -> None:
        self.beginResetModel()
        self._filas = list(filas)
        self.endResetModel()

    def planta_id(self, fila: int) -> int:
        return self._filas[fila].planta_id

    def rowCount(self, parent: _INDICE = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._filas)

    def columnCount(self, parent: _INDICE = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(ENCABEZADOS)

    def headerData(
        self, seccion: int, orientacion: Qt.Orientation, rol: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if orientacion == Qt.Orientation.Horizontal and rol == Qt.ItemDataRole.DisplayRole:
            return ENCABEZADOS[seccion]
        return None

    def data(self, indice: _INDICE, rol: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not indice.isValid():
            return None
        fila = self._filas[indice.row()]
        columna = Col(indice.column())

        if rol == Qt.ItemDataRole.DisplayRole:
            return {
                Col.NUMERO: fila.numero,
                Col.PLANTA: fila.planta,
                Col.ESTADO: fila.estado,
                Col.INGRESOS: formatear_moneda(fila.ingresos),
                Col.GASTOS: formatear_moneda(fila.gastos),
                Col.RESULTADO: formatear_moneda(fila.resultado),
                Col.DESGASTE: formatear_porcentaje(fila.desgaste) or "—",
                Col.SEMAFORO: fila.nivel_texto,
            }[columna]
        if rol == Qt.ItemDataRole.UserRole:  # Valor real para ordenar
            return {
                Col.NUMERO: fila.numero_orden,
                Col.PLANTA: fila.planta.casefold(),
                Col.ESTADO: fila.estado,
                Col.INGRESOS: fila.ingresos,
                Col.GASTOS: fila.gastos,
                Col.RESULTADO: fila.resultado,
                Col.DESGASTE: fila.desgaste if fila.desgaste is not None else -1.0,
                Col.SEMAFORO: _GRAVEDAD.get(fila.nivel, 9),
            }[columna]
        if rol == Qt.ItemDataRole.TextAlignmentRole and columna in (
            Col.INGRESOS,
            Col.GASTOS,
            Col.RESULTADO,
            Col.DESGASTE,
        ):
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if rol == Qt.ItemDataRole.ForegroundRole:
            if columna == Col.RESULTADO and fila.resultado < 0:
                return QBrush(QColor(SEMAFORO["EVALUAR_REEMPLAZO"][1]))
            if columna == Col.SEMAFORO:
                return QBrush(QColor(SEMAFORO.get(fila.nivel, SEMAFORO["SIN_DATOS"])[1]))
        if rol == Qt.ItemDataRole.DecorationRole and columna == Col.SEMAFORO:
            return self._iconos.get(fila.nivel)
        if rol == Qt.ItemDataRole.ToolTipRole:
            return fila.razones or None
        return None


def _punto(color: str) -> QIcon:
    """Círculo de color para la columna del semáforo."""
    lienzo = QPixmap(12, 12)
    lienzo.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(lienzo)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    pintor.setBrush(QColor(color))
    pintor.setPen(Qt.PenStyle.NoPen)
    pintor.drawEllipse(1, 1, 10, 10)
    pintor.end()
    return QIcon(lienzo)
