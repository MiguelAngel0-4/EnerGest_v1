"""
Pruebas unitarias del servicio de consecutivos.

Ruta: tests/unit/test_consecutivo_service.py
"""

import pytest

from src.business.services.consecutivo_service import ConsecutivoService


@pytest.mark.parametrize(
    ("en_uso", "esperado"),
    [
        (set(), 1),
        ({1, 2, 3}, 4),
        ({1, 3}, 2),
        ({2, 3}, 1),
        ({1, 2, 4, 5}, 3),
    ],
)
def test_calcular_menor_libre(en_uso: set[int], esperado: int) -> None:
    assert ConsecutivoService.calcular_menor_libre(en_uso) == esperado
