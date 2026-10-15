"""
Pruebas del formato de porcentajes (Actividad 4.4).

Ruta: tests/unit/test_formatters.py
"""

import pytest

from src.shared.formatters import formatear_porcentaje


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (None, None),
        (0, "0 %"),
        (0.18, "< 1 %"),  # Un desgaste pequeño no se muestra como "0 %"
        (1, "1 %"),
        (72.4, "72 %"),
        (60, "60 %"),
    ],
)
def test_formatear_porcentaje(valor, esperado) -> None:
    assert formatear_porcentaje(valor) == esperado
