"""
Pruebas unitarias de la máquina de estados.

Ruta: tests/unit/test_estado_planta.py
"""

import pytest

from src.business.models.estado_planta import EstadoPlanta as E


@pytest.mark.parametrize(
    ("origen", "destino"),
    [
        (E.DISPONIBLE, E.ALQUILADA),
        (E.DISPONIBLE, E.VENDIDA),
        (E.ALQUILADA, E.DISPONIBLE),
        (E.ALQUILADA, E.EN_MANTENIMIENTO),
        (E.EN_MANTENIMIENTO, E.DADA_DE_BAJA),
        (E.RETIRADA, E.DISPONIBLE),
        (E.RETIRADA, E.VENDIDA),
    ],
)
def test_transiciones_permitidas(origen: E, destino: E) -> None:
    assert origen.puede_pasar_a(destino)


@pytest.mark.parametrize(
    ("origen", "destino"),
    [
        (E.ALQUILADA, E.VENDIDA),  # Primero debe volver a disponible
        (E.EN_MANTENIMIENTO, E.ALQUILADA),
        (E.VENDIDA, E.DISPONIBLE),
        (E.DADA_DE_BAJA, E.DISPONIBLE),
        (E.DISPONIBLE, E.DISPONIBLE),  # Sin "cambios" al mismo estado
    ],
)
def test_transiciones_prohibidas(origen: E, destino: E) -> None:
    assert not origen.puede_pasar_a(destino)


def test_todos_los_estados_tienen_reglas_y_etiqueta() -> None:
    for estado in E:
        assert isinstance(estado.destinos_posibles(), frozenset)
        assert estado.etiqueta


def test_estados_finales() -> None:
    assert {e for e in E if e.es_final} == {E.VENDIDA, E.DADA_DE_BAJA}


def test_estados_fuera_de_operacion_requieren_motivo() -> None:
    fuera = {e for e in E if not e.en_operacion}
    assert fuera == {E.RETIRADA, E.VENDIDA, E.DADA_DE_BAJA}
    assert all(e.requiere_motivo for e in fuera)


def test_strenum_se_compara_con_texto_de_la_bd() -> None:
    assert E("VENDIDA") is E.VENDIDA
    assert E.VENDIDA == "VENDIDA"
