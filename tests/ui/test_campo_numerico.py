"""
Pruebas de regresión del campo numérico (defecto de la validación del MVP 1).

Ruta: tests/ui/test_campo_numerico.py
"""

import pytest
from PySide6.QtWidgets import QApplication

from src.presentation.widgets.campo_numerico import CampoNumerico
from tests.ui.conftest import escribir_como_usuario


@pytest.mark.parametrize(
    ("teclas", "esperado"),
    [
        ("48", 48.0),
        ("48,5", 48.5),  # Coma decimal (costumbre colombiana)
        ("48.5", 48.5),  # Punto decimal
        ("4a8", 48.0),  # Las letras se ignoran
        ("1,234", 1.23),  # Máximo 2 decimales
    ],
)
def test_decimal_acepta_escritura_real(qapp: QApplication, teclas: str, esperado: float) -> None:
    campo = CampoNumerico(decimales=2)
    campo.show()
    escribir_como_usuario(campo, teclas)
    assert campo.valor() == pytest.approx(esperado)


def test_vacio_significa_sin_dato(qapp: QApplication) -> None:
    assert CampoNumerico().valor() is None


@pytest.mark.parametrize("teclas", ["1200", "1.200"])
def test_entero_acepta_puntos_de_miles(qapp: QApplication, teclas: str) -> None:
    campo = CampoNumerico(decimales=0)
    campo.show()
    escribir_como_usuario(campo, teclas)
    campo.editingFinished.emit()
    assert campo.valor_entero() == 1200
    assert campo.text() == "1.200"


def test_set_valor_muestra_formato_colombiano(qapp: QApplication) -> None:
    campo = CampoNumerico(decimales=2)
    campo.set_valor(2.5)
    assert campo.text() == "2,5"
    campo.set_valor(None)
    assert campo.text() == ""


def test_el_simulador_de_teclado_rechaza_tildes_con_un_mensaje_claro(qapp: QApplication) -> None:
    """QTest no sabe teclear "é": sin esta guarda, Qt abortaría todo el proceso de pruebas."""
    campo = CampoNumerico()
    with pytest.raises(ValueError, match="solo admite texto ASCII"):
        escribir_como_usuario(campo, "Pérez")
