"""
Cálculos de calendario compartidos por las reglas de negocio.

Ruta: src/business/calendario.py

Los usan los mantenimientos (próximo preventivo en +6 meses) y los
alquileres (meses completos de una liquidación). Tenerlos en un solo lugar
garantiza que "un mes" signifique lo mismo en todo el sistema.
"""

import calendar
from datetime import date


def sumar_meses(fecha: date, meses: int) -> date:
    """
    Suma meses de calendario respetando el fin de mes.

    31 de enero + 1 mes = 28 (o 29) de febrero, no un "31 de febrero" inexistente.
    Siempre se calcula desde la fecha original: 31 de enero + 2 meses = 31 de marzo.
    """
    mes_total = fecha.month - 1 + meses
    anio, mes = fecha.year + mes_total // 12, mes_total % 12 + 1
    return date(anio, mes, min(fecha.day, calendar.monthrange(anio, mes)[1]))


def meses_y_dias(inicio: date, fin: date) -> tuple[int, int]:
    """
    Meses completos de calendario entre dos fechas y los días que sobran.

    Ej.: 01/10 -> 11/11 = (1, 10); 01/10 -> 01/12 = (2, 0); 31/01 -> 28/02 = (1, 0).
    """
    meses = 0
    while sumar_meses(inicio, meses + 1) <= fin:
        meses += 1
    return meses, (fin - sumar_meses(inicio, meses)).days
