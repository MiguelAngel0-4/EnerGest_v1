"""
Pruebas del semáforo de reemplazo (regla aprobada en la Actividad 4.4).

Ruta: tests/unit/test_indicador_reemplazo.py
"""

import pytest

from src.business.models.rentabilidad import NivelIndicador as N
from src.business.services.indicador_reemplazo import evaluar_reemplazo

COMPRA = 10_000_000


@pytest.mark.parametrize(
    ("gastos_acumulados", "ingresos_12m", "gastos_12m", "nivel"),
    [
        (2_000_000, 5_000_000, 1_000_000, N.RENTABLE),  # 20 % y con ganancia
        (6_000_000, 5_000_000, 1_000_000, N.VIGILAR),  # 60 % exacto: se activa
        (5_999_999, 5_000_000, 1_000_000, N.RENTABLE),  # Justo por debajo del umbral
        (2_000_000, 1_000_000, 1_500_000, N.VIGILAR),  # Solo pérdida reciente
        (7_200_000, 1_000_000, 1_500_000, N.EVALUAR_REEMPLAZO),  # Ambas señales
        (2_000_000, 1_000_000, 1_000_000, N.RENTABLE),  # Empate: no es pérdida
    ],
)
def test_niveles_del_semaforo(gastos_acumulados, ingresos_12m, gastos_12m, nivel) -> None:
    assert evaluar_reemplazo(COMPRA, gastos_acumulados, ingresos_12m, gastos_12m).nivel is nivel


def test_las_razones_explican_las_cifras() -> None:
    indicador = evaluar_reemplazo(COMPRA, 7_200_000, 1_000_000, 1_420_000)
    assert indicador.desgaste_pct == pytest.approx(72)
    assert indicador.resultado_reciente == -420_000
    assert "72 %" in indicador.razones[0]
    assert "$ 420.000" in indicador.razones[1]


def test_sin_valor_de_compra_solo_evalua_la_perdida_y_lo_advierte() -> None:
    indicador = evaluar_reemplazo(None, 50_000_000, 1_000_000, 2_000_000)
    assert indicador.nivel is N.VIGILAR
    assert indicador.desgaste_pct is None
    assert any("Sin valor de compra" in r for r in indicador.razones)


def test_planta_sin_movimientos_no_se_califica() -> None:
    assert evaluar_reemplazo(COMPRA, 0, 0, 0).nivel is N.SIN_DATOS


def test_planta_inactiva_con_gastos_es_vigilada() -> None:
    """Una planta en bodega que solo genera gastos: no produce, pero cuesta."""
    assert evaluar_reemplazo(COMPRA, 300_000, 0, 300_000).nivel is N.VIGILAR


def test_umbrales_configurables() -> None:
    indicador = evaluar_reemplazo(COMPRA, 4_000_000, 1_000_000, 0, umbral_desgaste=40, meses=6)
    assert indicador.nivel is N.VIGILAR and "40 %" in indicador.razones[0]
