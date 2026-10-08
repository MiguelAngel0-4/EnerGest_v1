"""
Pruebas de la liquidación de alquileres: los ejemplos aprobados en el diseño.

Ruta: tests/unit/test_liquidacion.py
"""

from datetime import date

import pytest

from src.business.calendario import meses_y_dias
from src.business.models.comercial import Liquidacion, ModalidadAlquiler
from src.business.services.liquidacion import calcular_liquidacion

MES, DIA = ModalidadAlquiler.MES, ModalidadAlquiler.DIA


@pytest.mark.parametrize(
    ("inicio", "fin", "meses", "dias", "valor"),
    [
        # Ejemplos exactos de la tabla aprobada (tarifa de $ 3.000.000 mensuales)
        (date(2026, 10, 1), date(2026, 11, 11), 1, 10, 4_000_000),
        (date(2026, 10, 1), date(2026, 10, 21), 0, 20, 2_000_000),
        (date(2026, 10, 1), date(2026, 12, 1), 2, 0, 6_000_000),
        (date(2027, 1, 31), date(2027, 2, 28), 1, 0, 3_000_000),
        (date(2026, 10, 5), date(2026, 10, 5), 0, 1, 100_000),  # Mínimo un día
    ],
)
def test_ejemplos_aprobados_por_mes(inicio, fin, meses, dias, valor) -> None:
    assert calcular_liquidacion(MES, 3_000_000, inicio, fin) == Liquidacion(meses, dias, valor)


def test_por_dia_cuenta_dias_con_minimo_uno() -> None:
    assert calcular_liquidacion(DIA, 180_000, date(2026, 10, 1), date(2026, 10, 13)).valor == (
        12 * 180_000
    )
    assert calcular_liquidacion(DIA, 180_000, date(2026, 10, 1), date(2026, 10, 1)).valor == 180_000


def test_redondeo_al_peso_mas_cercano() -> None:
    # 1 día de una tarifa mensual de $ 1.000.000 = 33.333,33 -> $ 33.333
    assert (
        calcular_liquidacion(MES, 1_000_000, date(2026, 10, 1), date(2026, 10, 2)).valor == 33_333
    )
    # 1 día de $ 1.000.005 = 33.333,5 -> se redondea hacia arriba: $ 33.334
    assert (
        calcular_liquidacion(MES, 1_000_005, date(2026, 10, 1), date(2026, 10, 2)).valor == 33_334
    )


def test_fin_de_mes_se_cuenta_desde_la_fecha_original() -> None:
    # 31/01 + 2 meses = 31/03 (no 28/03): del 31/01 al 30/03 es 1 mes y 30 días
    assert meses_y_dias(date(2027, 1, 31), date(2027, 3, 30)) == (1, 30)
    assert meses_y_dias(date(2027, 1, 31), date(2027, 3, 31)) == (2, 0)


def test_devolucion_anterior_a_la_entrega_es_un_error() -> None:
    with pytest.raises(ValueError):
        calcular_liquidacion(DIA, 1000, date(2026, 10, 5), date(2026, 10, 1))
