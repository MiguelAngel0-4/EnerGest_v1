"""
Delegado que dibuja botones de acción dentro de una celda de tabla.

Ruta: src/presentation/widgets/acciones_delegate.py

Un "delegado" es el pintor de una celda: decide cómo se ve y cómo responde
a los clics. En lugar de crear botones reales por cada fila (pesados y
frágiles al filtrar u ordenar), este delegado los DIBUJA y detecta en
cuál se hizo clic según la posición del mouse.
"""

from typing import Final

from PySide6.QtCore import (
    QAbstractItemModel,
    QEvent,
    QModelIndex,
    QObject,
    QRect,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QMouseEvent, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionButton,
    QStyleOptionViewItem,
)

_MARGEN: Final[int] = 4
_ANCHO_BOTON: Final[int] = 66


class AccionesDelegate(QStyledItemDelegate):
    """Dibuja un botón por acción y emite accion_solicitada(clave, id) al hacer clic."""

    accion_solicitada = Signal(str, int)

    def __init__(
        self,
        acciones: list[tuple[str, str]],
        id_role: int,
        parent: QObject | None = None,
    ) -> None:
        """
        Args:
            acciones: Lista de (clave, texto visible), ej. [("editar", "Editar")].
            id_role: Rol del modelo que entrega el id del registro de la fila.
        """
        super().__init__(parent)
        self._acciones = acciones
        self._id_role = id_role

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        # Primero el fondo normal de la celda (respeta selección y filas alternas).
        super().paint(painter, option, index)
        estilo = option.widget.style() if option.widget else QApplication.style()
        for rect, (_clave, texto) in zip(self._rectangulos(option.rect), self._acciones):
            boton = QStyleOptionButton()
            boton.rect = rect
            boton.text = texto
            boton.state = QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_Raised
            estilo.drawControl(QStyle.ControlElement.CE_PushButton, boton, painter, option.widget)

    def editorEvent(
        self,
        event: QEvent,
        model: QAbstractItemModel,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> bool:
        if (
            event.type() == QEvent.Type.MouseButtonRelease
            and isinstance(event, QMouseEvent)
            and event.button() == Qt.MouseButton.LeftButton
        ):
            punto = event.position().toPoint()
            for rect, (clave, _texto) in zip(self._rectangulos(option.rect), self._acciones):
                if rect.contains(punto):
                    registro_id = index.data(self._id_role)
                    if registro_id is not None:
                        self.accion_solicitada.emit(clave, int(registro_id))
                    return True
        return super().editorEvent(event, model, option, index)

    def ancho_requerido(self) -> int:
        """Ancho en píxeles que necesita la columna para mostrar todos los botones."""
        return len(self._acciones) * (_ANCHO_BOTON + _MARGEN) + _MARGEN

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        return QSize(self.ancho_requerido(), 32)

    def _rectangulos(self, area: QRect) -> list[QRect]:
        """Calcula la posición de cada botón dentro de la celda."""
        alto = max(area.height() - 2 * _MARGEN, 18)
        y = area.top() + (area.height() - alto) // 2
        return [
            QRect(area.left() + _MARGEN + i * (_ANCHO_BOTON + _MARGEN), y, _ANCHO_BOTON, alto)
            for i in range(len(self._acciones))
        ]
