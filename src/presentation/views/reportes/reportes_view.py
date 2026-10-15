"""
Pantalla "Reportes financieros" (Propuesta 3 del wireframe).

Ruta: src/presentation/views/reportes/reportes_view.py

De arriba abajo: período y exportación, cuatro tarjetas con las cifras del
período, el gráfico mensual de ingresos frente a gastos y la tabla por
planta con su semáforo. Vista pasiva: recibe datos formateados y avisa con
señales lo que el usuario pide.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import NamedTuple

from PySide6.QtCharts import QBarCategoryAxis, QBarSeries, QBarSet, QChart, QChartView, QValueAxis
from PySide6.QtCore import QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QShowEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from src.presentation.table_models.reporte_table_model import (
    Col,
    FilaTablaReporte,
    ReporteTableModel,
)
from src.presentation.widgets.selector_periodo import SelectorPeriodo
from src.shared.colores import GASTOS, INGRESOS, SEMAFORO


class Tarjeta(NamedTuple):
    titulo: str
    valor: str
    detalle: str = ""
    negativo: bool = False


class ReportesView(QWidget):
    periodo_cambiado = Signal()
    incluir_cambiado = Signal()
    exportar_solicitado = Signal()
    planta_seleccionada = Signal(int)  # Doble clic en una fila
    mostrada = Signal()  # La pantalla se hizo visible: hay que recargar

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        titulo = QLabel("Reportes financieros")
        titulo.setObjectName("tituloVista")

        self.periodo = SelectorPeriodo()
        self._incluir = QCheckBox("Incluir plantas vendidas o dadas de baja")
        self._incluir.setChecked(True)
        boton_exportar = QPushButton("Exportar a Excel")
        boton_exportar.setObjectName("botonPrimario")
        barra = QHBoxLayout()
        barra.addWidget(self.periodo)
        barra.addSpacing(16)
        barra.addWidget(self._incluir)
        barra.addStretch()
        barra.addWidget(boton_exportar)

        self._tarjetas = QHBoxLayout()
        self._tarjetas.setSpacing(12)

        self._grafico = QChartView()
        self._grafico.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._grafico.setMinimumHeight(230)
        self._sin_movimientos = QLabel("No hay ingresos ni gastos en el período elegido.")
        self._sin_movimientos.setObjectName("textoSecundario")
        self._sin_movimientos.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sin_movimientos.hide()

        self.modelo = ReporteTableModel()
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self.modelo)
        self._proxy.setSortRole(Qt.ItemDataRole.UserRole)  # Ordena por el valor real
        self.tabla = QTableView()
        self.tabla.setModel(self._proxy)
        self.tabla.setSortingEnabled(True)
        self.tabla.sortByColumn(Col.SEMAFORO, Qt.SortOrder.AscendingOrder)  # Lo más grave arriba
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.setToolTip("Doble clic para abrir el balance de la planta.")
        encabezado = self.tabla.horizontalHeader()
        encabezado.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        encabezado.setSectionResizeMode(Col.PLANTA, QHeaderView.ResizeMode.Stretch)

        self._pie = QLabel()
        self._pie.setObjectName("textoSecundario")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 12)
        layout.addWidget(titulo)
        layout.addLayout(barra)
        layout.addLayout(self._tarjetas)
        layout.addWidget(self._grafico, stretch=2)
        layout.addWidget(self._sin_movimientos)
        layout.addWidget(self.tabla, stretch=3)
        layout.addWidget(self._pie)

        self.periodo.periodo_cambiado.connect(self.periodo_cambiado)
        self._incluir.toggled.connect(lambda _v: self.incluir_cambiado.emit())
        boton_exportar.clicked.connect(self.exportar_solicitado)
        self.tabla.doubleClicked.connect(
            lambda indice: self.planta_seleccionada.emit(
                self.modelo.planta_id(self._proxy.mapToSource(indice).row())
            )
        )

    def showEvent(self, evento: QShowEvent) -> None:  # Nombre impuesto por Qt
        super().showEvent(evento)
        self.mostrada.emit()

    # --- API pública ------------------------------------------------------

    def incluir_fuera_de_operacion(self) -> bool:
        return self._incluir.isChecked()

    def mostrar_tarjetas(self, tarjetas: list[Tarjeta]) -> None:
        while self._tarjetas.count():
            elemento = self._tarjetas.takeAt(0)
            if elemento.widget() is not None:
                elemento.widget().deleteLater()
        for tarjeta in tarjetas:
            marco = QFrame()
            marco.setObjectName("tarjeta")
            titulo = QLabel(tarjeta.titulo)
            titulo.setObjectName("textoSecundario")
            valor = QLabel(tarjeta.valor)
            valor.setObjectName("valorTarjeta")
            if tarjeta.negativo:
                valor.setStyleSheet(f"color: {SEMAFORO['EVALUAR_REEMPLAZO'][1]};")
            layout = QVBoxLayout(marco)
            layout.addWidget(titulo)
            layout.addWidget(valor)
            if tarjeta.detalle:
                detalle = QLabel(tarjeta.detalle)
                detalle.setObjectName("textoSecundario")
                layout.addWidget(detalle)
            self._tarjetas.addWidget(marco, stretch=1)

    def mostrar_meses(self, etiquetas: list[str], ingresos: list[int], gastos: list[int]) -> None:
        """Barras agrupadas por mes, en millones de pesos."""
        hay_datos = bool(etiquetas)
        self._grafico.setVisible(hay_datos)
        self._sin_movimientos.setVisible(not hay_datos)
        grafico = QChart()
        grafico.setTitle("Ingresos y gastos por mes (millones de $)")
        grafico.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        grafico.setAnimationOptions(QChart.AnimationOption.NoAnimation)
        if hay_datos:
            serie = QBarSeries()
            for nombre, valores, color in (
                ("Ingresos", ingresos, INGRESOS),
                ("Gastos", gastos, GASTOS),
            ):
                barras = QBarSet(nombre)
                barras.setColor(QColor(color))
                barras.append([v / 1_000_000 for v in valores])
                serie.append(barras)
            grafico.addSeries(serie)
            eje_x = QBarCategoryAxis()
            eje_x.append(etiquetas)
            eje_y = QValueAxis()
            maximo = max([*ingresos, *gastos, 1]) / 1_000_000
            eje_y.setRange(0, maximo * 1.1)
            eje_y.applyNiceNumbers()  # Marcas "redondas": 0, 20, 40... en vez de 18,1; 36,2...
            eje_y.setLabelFormat("%.0f" if maximo >= 5 else "%.1f")
            grafico.addAxis(eje_x, Qt.AlignmentFlag.AlignBottom)
            grafico.addAxis(eje_y, Qt.AlignmentFlag.AlignLeft)
            serie.attachAxis(eje_x)
            serie.attachAxis(eje_y)
        anterior = self._grafico.chart()
        self._grafico.setChart(grafico)
        if anterior is not None:
            anterior.deleteLater()

    def mostrar_filas(self, filas: list[FilaTablaReporte]) -> None:
        self.modelo.cargar(filas)

    def mostrar_pie(self, texto: str) -> None:
        self._pie.setText(texto)

    def pedir_ruta_guardado(self, sugerida: str) -> str | None:
        ruta, _filtro = QFileDialog.getSaveFileName(
            self, "Exportar reporte a Excel", sugerida, "Libro de Excel (*.xlsx)"
        )
        if not ruta:
            return None
        return ruta if ruta.lower().endswith(".xlsx") else f"{ruta}.xlsx"

    def preguntar_abrir(self, ruta: str) -> bool:
        respuesta = QMessageBox.question(
            self,
            "Reporte exportado",
            f"El reporte se guardó en:\n{ruta}\n\n¿Desea abrirlo ahora?",
        )
        return respuesta == QMessageBox.StandardButton.Yes

    def mostrar_error(self, titulo: str, mensaje: str) -> None:
        QMessageBox.warning(self, titulo, mensaje)

    @contextmanager
    def cursor_espera(self) -> Iterator[None]:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            yield
        finally:
            QApplication.restoreOverrideCursor()
