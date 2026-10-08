"""
Cálculo de la liquidación de un alquiler (regla aprobada en la Actividad 4.3).

Ruta: src/business/services/liquidacion.py

Se cobra el tiempo real de uso, nunca un mes completo que no se usó:
- Por día: días entre la entrega y la devolución, mínimo 1.
- Por mes: meses completos de calendario × tarifa + días restantes × tarifa / 30
  (mes comercial), redondeado al peso. Mínimo 1 día.

Es una función pura (sin base de datos): se prueba con cualquier par de fechas.
"""

from datetime import date
from typing import Final

from src.business.calendario import meses_y_dias
from src.business.models.comercial import Liquidacion, ModalidadAlquiler

DIAS_MES_COMERCIAL: Final[int] = 30


def calcular_liquidacion(
    modalidad: ModalidadAlquiler, tarifa: int, inicio: date, fin: date
) -> Liquidacion:
    if fin < inicio:
        raise ValueError("La fecha de devolución no puede ser anterior a la de entrega.")

    if modalidad is ModalidadAlquiler.DIA:
        dias = max((fin - inicio).days, 1)
        return Liquidacion(meses=0, dias=dias, valor=dias * tarifa)

    meses, dias = meses_y_dias(inicio, fin)
    if meses == 0 and dias == 0:
        dias = 1  # Mínimo un día
    # Redondeo "al peso más cercano" en enteros: (2a + b) // 2b es la mitad hacia arriba.
    valor_dias = (2 * dias * tarifa + DIAS_MES_COMERCIAL) // (2 * DIAS_MES_COMERCIAL)
    return Liquidacion(meses=meses, dias=dias, valor=meses * tarifa + valor_dias)
