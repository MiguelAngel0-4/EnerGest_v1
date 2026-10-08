"""
Casos de uso de rentabilidad (Actividad 4.4).

Ruta: src/business/services/rentabilidad_service.py

Reúne ingresos, gastos, horas de uso y saldos para responder la pregunta que
dio origen al proyecto: ¿conviene mantener o reemplazar cada planta?

El semáforo SIEMPRE se calcula con toda la vida de la planta y la ventana
reciente (por ejemplo, 12 meses), sin importar el período que el usuario
esté consultando: una planta no deja de "necesitar reemplazo" porque alguien
mire solo el mes pasado.
"""

import logging
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import Protocol

from src.business.calendario import sumar_meses
from src.business.exceptions import PlantaNoEncontradaError
from src.business.interfaces.unidad_de_trabajo import FabricaUnidadDeTrabajo, IUnidadDeTrabajo
from src.business.models.estado_planta import EstadoPlanta
from src.business.models.planta import Planta
from src.business.models.rentabilidad import (
    BalancePlanta,
    FilaReporte,
    Indicador,
    Movimiento,
    Periodo,
    ResumenFinanciero,
    TotalesPlanta,
)
from src.business.services.indicador_reemplazo import evaluar_reemplazo

logger = logging.getLogger(__name__)


class IExportadorReporte(Protocol):
    """Convierte un resumen financiero y sus movimientos en un archivo."""

    def exportar(
        self, resumen: ResumenFinanciero, movimientos: list[Movimiento], destino: Path
    ) -> Path:
        """Raises: DocumentoError si el archivo no se pudo escribir."""
        ...


class RentabilidadService:
    def __init__(
        self,
        uow_factory: FabricaUnidadDeTrabajo,
        hoy: Callable[[], date] = date.today,
        umbral_desgaste: int = 60,
        meses_perdida: int = 12,
    ) -> None:
        """
        Args:
            umbral_desgaste / meses_perdida: criterios del semáforo
                (en la aplicación vienen de settings.py).
        """
        self._uow_factory = uow_factory
        self._hoy = hoy
        self._umbral = umbral_desgaste
        self._meses = meses_perdida

    def balance(self, planta_id: int, periodo: Periodo = Periodo()) -> BalancePlanta:
        """Todo lo que la pestaña Balance muestra de una planta."""
        with self._uow_factory() as uow:
            planta = uow.plantas.obtener(planta_id)
            if planta is None:
                raise PlantaNoEncontradaError(planta_id)
            reportes = uow.reportes
            totales = reportes.totales_por_planta(periodo.desde, periodo.hasta).get(
                planta_id, TotalesPlanta()
            )
            indicador = self._indicadores(uow, [planta])[planta_id]
            return BalancePlanta(
                planta=planta,
                periodo=periodo,
                totales=totales,
                gastos_por_categoria=tuple(
                    reportes.gastos_por_categoria(planta_id, periodo.desde, periodo.hasta)
                ),
                horas_uso_alquiler=reportes.horas_uso_alquiler(
                    planta_id, periodo.desde, periodo.hasta
                ),
                saldo_por_cobrar=reportes.saldo_por_cobrar(planta_id),
                indicador=indicador,
            )

    def resumen(
        self, periodo: Periodo = Periodo(), incluir_fuera_de_operacion: bool = True
    ) -> ResumenFinanciero:
        """Tarjetas, gráfico mensual y tabla por planta de un período."""
        estados = (
            None if incluir_fuera_de_operacion else {e for e in EstadoPlanta if e.en_operacion}
        )
        with self._uow_factory() as uow:
            plantas = uow.plantas.listar(estados)
            totales = uow.reportes.totales_por_planta(periodo.desde, periodo.hasta)
            indicadores = self._indicadores(uow, plantas)
            meses = uow.reportes.meses(periodo.desde, periodo.hasta)
            saldo = uow.reportes.saldo_por_cobrar()

        filas = tuple(
            FilaReporte(p, totales.get(p.id, TotalesPlanta()), indicadores[p.id]) for p in plantas
        )
        # Las tarjetas suman las plantas mostradas: total = suma de la tabla.
        ingresos = sum(f.totales.ingresos_operacion + f.totales.ingresos_venta for f in filas)
        gastos = sum(f.totales.gastos for f in filas)
        return ResumenFinanciero(periodo, ingresos, gastos, saldo, tuple(meses), filas)

    def movimientos(self, periodo: Periodo = Periodo()) -> list[Movimiento]:
        with self._uow_factory() as uow:
            return uow.reportes.movimientos(periodo.desde, periodo.hasta)

    def exportar(self, periodo: Periodo, exportador: IExportadorReporte, destino: Path) -> Path:
        """Raises: DocumentoError"""
        ruta = exportador.exportar(self.resumen(periodo), self.movimientos(periodo), destino)
        logger.info("Reporte financiero exportado a %s", ruta)
        return ruta

    def periodo_reciente(self) -> Periodo:
        """La ventana del semáforo: los últimos N meses hasta hoy."""
        hoy = self._hoy()
        return Periodo(sumar_meses(hoy, -self._meses) + timedelta(days=1), hoy)

    def _indicadores(self, uow: IUnidadDeTrabajo, plantas: list[Planta]) -> dict[int, Indicador]:
        """Semáforo de cada planta: toda la vida + ventana reciente (2 consultas en total)."""
        vida = uow.reportes.totales_por_planta()
        reciente_periodo = self.periodo_reciente()
        reciente = uow.reportes.totales_por_planta(reciente_periodo.desde, reciente_periodo.hasta)
        resultado: dict[int, Indicador] = {}
        for planta in plantas:
            de_por_vida = vida.get(planta.id, TotalesPlanta())
            recientes = reciente.get(planta.id, TotalesPlanta())
            resultado[planta.id] = evaluar_reemplazo(
                planta.datos.valor_compra,
                de_por_vida.gastos,
                recientes.ingresos_operacion,
                recientes.gastos,
                self._umbral,
                self._meses,
            )
        return resultado
