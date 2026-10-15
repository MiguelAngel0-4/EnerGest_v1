"""
Semáforo de reemplazo (regla aprobada en la Actividad 4.4).

Ruta: src/business/services/indicador_reemplazo.py

Dos señales, las que usaría el dueño de un taxi:
- Desgaste acumulado: los gastos de toda la vida alcanzan el X % del valor de compra.
- Pérdida reciente: en los últimos N meses, los gastos superan los ingresos.

Ninguna señal = Rentable; una = Vigilar; ambas = Evaluar reemplazo.
Es una función pura: se prueba con cualquier combinación de cifras.
"""

from src.business.models.rentabilidad import Indicador, NivelIndicador
from src.shared.formatters import formatear_moneda


def evaluar_reemplazo(
    valor_compra: int | None,
    gastos_acumulados: int,
    ingresos_recientes: int,
    gastos_recientes: int,
    umbral_desgaste: int = 60,
    meses: int = 12,
) -> Indicador:
    resultado_reciente = ingresos_recientes - gastos_recientes
    sin_movimientos = gastos_acumulados == 0 and ingresos_recientes == 0 and gastos_recientes == 0
    desgaste = gastos_acumulados * 100 / valor_compra if valor_compra else None

    if sin_movimientos:
        return Indicador(
            NivelIndicador.SIN_DATOS,
            ("La planta aún no tiene ingresos ni gastos registrados.",),
            desgaste,
            0,
        )

    razones: list[str] = []
    senal_desgaste = desgaste is not None and desgaste >= umbral_desgaste
    if senal_desgaste:
        razones.append(
            f"Sus gastos acumulados equivalen al {desgaste:.0f} % de su valor de compra "
            f"(umbral: {umbral_desgaste} %)."
        )
    senal_perdida = gastos_recientes > ingresos_recientes
    if senal_perdida:
        razones.append(
            f"En los últimos {meses} meses los gastos superaron los ingresos en "
            f"{formatear_moneda(-resultado_reciente)}."
        )
    if valor_compra is None:
        razones.append("Sin valor de compra registrado: solo se evalúa la pérdida reciente.")

    senales = int(senal_desgaste) + int(senal_perdida)
    nivel = {
        0: NivelIndicador.RENTABLE,
        1: NivelIndicador.VIGILAR,
        2: NivelIndicador.EVALUAR_REEMPLAZO,
    }[senales]
    return Indicador(nivel, tuple(razones), desgaste, resultado_reciente)
