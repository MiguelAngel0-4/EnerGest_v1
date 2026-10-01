"""
Modelo de tabla y proxy de filtros del inventario de plantas.

Ruta: src/presentation/table_models/plantas_table_model.py

Qt usa el patrón Modelo-Vista: el QTableView solo DIBUJA; este modelo le
dice qué mostrar en cada celda. Es como el guion que lee un presentador:
el presentador (la tabla) no inventa nada, solo lee lo que dice el guion.

Roles: una misma celda puede entregar varios datos según quién pregunte.
- DisplayRole: el texto visible ("250 kVA").
- ORDEN_ROLE: el valor crudo para ordenar (250.0), no el texto.
- ID_ROLE, ESTADO_ROLE...: datos internos para filtros y acciones.
"""

from enum import IntEnum
from typing import Any, Final

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QSortFilterProxyModel,
    Qt,
)
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPixmap

from src.business.models.estado_planta import EstadoPlanta
from src.business.models.planta import Planta
from src.shared.formatters import (
    SIN_VALOR,
    formatear_consecutivo,
    formatear_decimal,
    formatear_entero,
)

ModelIndex = QModelIndex | QPersistentModelIndex


class Columna(IntEnum):
    """Columnas de la tabla, en orden de aparición."""

    CONSECUTIVO = 0
    MARCA = 1
    MODELO = 2
    POTENCIA = 3
    SERIAL = 4
    HOROMETRO = 5
    ESTADO = 6
    ACCIONES = 7


_ENCABEZADOS: Final[dict[Columna, str]] = {
    Columna.CONSECUTIVO: "N°\nConsecutivo",  # Dos líneas, como el wireframe
    Columna.MARCA: "Marca",
    Columna.MODELO: "Modelo",
    Columna.POTENCIA: "Potencia\n(kVA)",
    Columna.SERIAL: "Serial",
    Columna.HOROMETRO: "Horómetro",
    Columna.ESTADO: "Estado",
    Columna.ACCIONES: "Acciones",
}

# Roles personalizados (a partir de UserRole, reservado para la aplicación).
ID_ROLE: Final[int] = Qt.ItemDataRole.UserRole + 1
ORDEN_ROLE: Final[int] = Qt.ItemDataRole.UserRole + 2
ESTADO_ROLE: Final[int] = Qt.ItemDataRole.UserRole + 3
MARCA_ROLE: Final[int] = Qt.ItemDataRole.UserRole + 4
POTENCIA_ROLE: Final[int] = Qt.ItemDataRole.UserRole + 5

COLORES_ESTADO: Final[dict[EstadoPlanta, str]] = {
    EstadoPlanta.DISPONIBLE: "#2E9E5B",
    EstadoPlanta.ALQUILADA: "#2E75B6",
    EstadoPlanta.EN_MANTENIMIENTO: "#E08A00",
    EstadoPlanta.RETIRADA: "#8A939B",
    EstadoPlanta.VENDIDA: "#8A939B",
    EstadoPlanta.DADA_DE_BAJA: "#8A939B",
}

# Rangos del filtro de potencia: clave -> (mínimo exclusivo, máximo inclusivo).
RANGOS_POTENCIA: Final[dict[str, tuple[str, float, float]]] = {
    "HASTA_50": ("Hasta 50 kVA", 0.0, 50.0),
    "51_150": ("51 – 150 kVA", 50.0, 150.0),
    "151_500": ("151 – 500 kVA", 150.0, 500.0),
    "MAS_500": ("Más de 500 kVA", 500.0, float("inf")),
}

_COLUMNAS_CENTRADAS: Final[frozenset[Columna]] = frozenset(
    {Columna.CONSECUTIVO, Columna.POTENCIA, Columna.HOROMETRO}
)
_COLOR_FUERA_DE_OPERACION: Final[str] = "#6C757D"


class PlantasTableModel(QAbstractTableModel):
    """Adapta una lista de Planta al formato de filas y columnas de Qt."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._plantas: list[Planta] = []
        self._iconos: dict[EstadoPlanta, QIcon] = {}

    def cargar(self, plantas: list[Planta]) -> None:
        """Reemplaza todo el contenido y avisa a la tabla que se redibuje."""
        self.beginResetModel()
        self._plantas = list(plantas)
        self.endResetModel()

    @property
    def plantas(self) -> list[Planta]:
        """Copia de las plantas cargadas."""
        return list(self._plantas)

    # --- Métodos obligatorios de QAbstractTableModel ---------------------------
    # Van en camelCase (rowCount, headerData...) porque SOBRESCRIBEN métodos de Qt:
    # Qt los llama por ese nombre exacto, así que no se pueden traducir.


    def rowCount(self, parent: ModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._plantas)

    def columnCount(self, parent: ModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(Columna)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return _ENCABEZADOS[Columna(section)]
        return None

    def data(self, index: ModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        planta = self._plantas[index.row()]
        columna = Columna(index.column())

        if role == Qt.ItemDataRole.DisplayRole:
            return self._texto(planta, columna)
        if role == ORDEN_ROLE:
            return self._valor_orden(planta, columna)
        if role == ID_ROLE:
            return planta.id
        if role == ESTADO_ROLE:
            return planta.estado.value
        if role == MARCA_ROLE:
            return planta.datos.marca
        if role == POTENCIA_ROLE:
            return planta.datos.potencia_kva
        if role == Qt.ItemDataRole.DecorationRole and columna == Columna.ESTADO:
            return self._icono_estado(planta.estado)
        if role == Qt.ItemDataRole.TextAlignmentRole and columna in _COLUMNAS_CENTRADAS:
            return int(Qt.AlignmentFlag.AlignCenter)
        if role == Qt.ItemDataRole.ForegroundRole and not planta.estado.en_operacion:
            return QBrush(QColor(_COLOR_FUERA_DE_OPERACION))  # Plantas inactivas en gris
        return None

    # --- Métodos internos ------------------------------------------------------

    @staticmethod
    def _texto(planta: Planta, columna: Columna) -> str:
        datos = planta.datos
        textos: dict[Columna, str] = {
            Columna.CONSECUTIVO: formatear_consecutivo(planta.numero_consecutivo),
            Columna.MARCA: datos.marca,
            Columna.MODELO: datos.modelo or SIN_VALOR,
            Columna.POTENCIA: formatear_decimal(datos.potencia_kva, "kVA"),
            Columna.SERIAL: datos.numero_serie or SIN_VALOR,
            Columna.HOROMETRO: formatear_entero(datos.horometro_inicial, "h"),
            Columna.ESTADO: planta.estado.etiqueta,
            Columna.ACCIONES: "",
        }
        return textos[columna]

    @staticmethod
    def _valor_orden(planta: Planta, columna: Columna) -> Any:
        """Valor crudo para ordenar: así 100 kVA queda después de 50 kVA (y no antes)."""
        datos = planta.datos
        valores: dict[Columna, Any] = {
            # Las plantas sin número se ordenan al final.
            Columna.CONSECUTIVO: planta.numero_consecutivo or 10**9,
            Columna.MARCA: datos.marca.casefold(),
            Columna.MODELO: (datos.modelo or "").casefold(),
            Columna.POTENCIA: datos.potencia_kva,
            Columna.SERIAL: (datos.numero_serie or "").casefold(),
            Columna.HOROMETRO: datos.horometro_inicial,
            Columna.ESTADO: planta.estado.etiqueta,
            Columna.ACCIONES: 0,
        }
        return valores[columna]

    def _icono_estado(self, estado: EstadoPlanta) -> QIcon:
        """Círculo de color del estado. Se dibuja una sola vez y se reutiliza."""
        if estado not in self._iconos:
            pixmap = QPixmap(12, 12)
            pixmap.fill(Qt.GlobalColor.transparent)
            pintor = QPainter(pixmap)
            pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
            pintor.setBrush(QColor(COLORES_ESTADO[estado]))
            pintor.setPen(Qt.PenStyle.NoPen)
            pintor.drawEllipse(1, 1, 10, 10)
            pintor.end()
            self._iconos[estado] = QIcon(pixmap)
        return self._iconos[estado]


class PlantasFilterProxy(QSortFilterProxyModel):
    """
    Capa intermedia entre el modelo y la tabla que filtra y ordena en memoria,
    sin volver a consultar la base de datos. Es como un colador: los datos
    pasan por él y la tabla solo recibe lo que cumple los filtros.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._estados: set[str] | None = None
        self._marca: str | None = None
        self._rango: tuple[float, float] | None = None
        self.setSortRole(ORDEN_ROLE)

    def filtrar(
        self,
        estados: set[str] | None,
        marca: str | None,
        rango_potencia: tuple[float, float] | None,
    ) -> None:
        """Aplica los filtros. None en un parámetro significa "no filtrar por eso"."""
        # beginFilterChange existe desde Qt 6.10; en versiones previas se usa
        # invalidateFilter. Así el código funciona con cualquier PySide6 >= 6.7.
        api_moderna = hasattr(self, "beginFilterChange")
        if api_moderna:
            self.beginFilterChange()
        self._estados = estados
        self._marca = marca.casefold() if marca else None
        self._rango = rango_potencia
        if api_moderna:
            self.endFilterChange()
        else:
            self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: ModelIndex) -> bool:
        modelo = self.sourceModel()
        indice = modelo.index(source_row, 0, source_parent)

        if self._estados is not None and modelo.data(indice, ESTADO_ROLE) not in self._estados:
            return False
        if self._marca is not None and str(modelo.data(indice, MARCA_ROLE)).casefold() != self._marca:
            return False
        if self._rango is not None:
            minimo, maximo = self._rango
            if not minimo < float(modelo.data(indice, POTENCIA_ROLE)) <= maximo:
                return False
        return True
