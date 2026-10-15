"""
Modelos de rentabilidad (Actividad 4.4).

Ruta: src/business/models/rentabilidad.py

Como el dueño de un taxi, cada planta responde dos preguntas distintas:
1. ¿Cuánto deja?          -> resultado de operación (ingresos - gastos).
2. ¿Ya pagó lo que costó? -> recuperación de la inversión.
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from src.business.models.planta import Planta


@dataclass(frozen=True, slots=True)
class Periodo:
    """Rango de fechas inclusivo. None en un extremo = sin límite por ese lado."""

    desde: date | None = None
    hasta: date | None = None

    @property
    def es_todo(self) -> bool:
        return self.desde is None and self.hasta is None


class NivelIndicador(StrEnum):
    RENTABLE = "RENTABLE"
    VIGILAR = "VIGILAR"
    EVALUAR_REEMPLAZO = "EVALUAR_REEMPLAZO"
    SIN_DATOS = "SIN_DATOS"

    @property
    def etiqueta(self) -> str:
        return {
            "RENTABLE": "Rentable",
            "VIGILAR": "Vigilar",
            "EVALUAR_REEMPLAZO": "Evaluar reemplazo",
            "SIN_DATOS": "Sin datos suficientes",
        }[self.value]


@dataclass(frozen=True, slots=True)
class Indicador:
    """Diagnóstico del semáforo: sugiere, no decide."""

    nivel: NivelIndicador
    razones: tuple[str, ...]
    desgaste_pct: float | None  # Gastos acumulados / valor de compra × 100
    resultado_reciente: int  # Ingresos - gastos de la ventana reciente


@dataclass(frozen=True, slots=True)
class TotalesPlanta:
    """Sumas de una planta en un período (solo movimientos vigentes)."""

    ingresos_alquiler: int = 0
    ingresos_venta: int = 0
    ingresos_otros: int = 0
    gastos: int = 0

    @property
    def ingresos_operacion(self) -> int:
        """Lo que produce operando: alquileres y otros (sin la venta)."""
        return self.ingresos_alquiler + self.ingresos_otros

    @property
    def resultado_operacion(self) -> int:
        return self.ingresos_operacion - self.gastos


@dataclass(frozen=True, slots=True)
class BalancePlanta:
    """Todo lo que la pestaña Balance necesita de una planta."""

    planta: Planta
    periodo: Periodo
    totales: TotalesPlanta
    gastos_por_categoria: tuple[tuple[str, int], ...]
    horas_uso_alquiler: int
    saldo_por_cobrar: int
    indicador: Indicador

    @property
    def recuperacion(self) -> int | None:
        """Resultado de operación + venta - valor de compra (None sin valor de compra)."""
        valor_compra = self.planta.datos.valor_compra
        if valor_compra is None:
            return None
        return self.totales.resultado_operacion + self.totales.ingresos_venta - valor_compra

    @property
    def ingreso_por_hora(self) -> int | None:
        if not self.horas_uso_alquiler:
            return None
        return round(self.totales.ingresos_alquiler / self.horas_uso_alquiler)


@dataclass(frozen=True, slots=True)
class FilaReporte:
    """Una planta en la tabla de Reportes financieros."""

    planta: Planta
    totales: TotalesPlanta
    indicador: Indicador


@dataclass(frozen=True, slots=True)
class MesFinanciero:
    mes: str  # "AAAA-MM"
    ingresos: int
    gastos: int


@dataclass(frozen=True, slots=True)
class ResumenFinanciero:
    """Vista global de un período: tarjetas, gráfico y tabla por planta."""

    periodo: Periodo
    ingresos: int
    gastos: int
    saldo_por_cobrar: int
    meses: tuple[MesFinanciero, ...]
    filas: tuple[FilaReporte, ...]

    @property
    def resultado(self) -> int:
        return self.ingresos - self.gastos


@dataclass(frozen=True, slots=True)
class Movimiento:
    """Una línea del detalle exportable: un ingreso o un gasto vigente."""

    fecha: date
    planta: str  # Ej. "PE-004 · Perkins P110"
    tipo: str  # "Ingreso" o "Gasto"
    concepto: str  # Tipo de ingreso o categoría de gasto
    descripcion: str
    documento: str | None
    valor: int
