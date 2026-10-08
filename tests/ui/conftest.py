"""
Configuración compartida de las pruebas de interfaz.

Ruta: tests/ui/conftest.py

Las pruebas de interfaz crean ventanas reales de Qt, pero en modo
"offscreen" (sin dibujarlas en pantalla), así que corren rápido y sin
abrir ventanas mientras trabajas.
"""

import os

# Debe definirse ANTES de crear la QApplication.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """Una sola QApplication para toda la sesión de pruebas (Qt no admite dos)."""
    app = QApplication.instance()
    return app if isinstance(app, QApplication) else QApplication([])


def escribir_como_usuario(widget: QWidget, texto: str) -> None:
    """
    Simula a una persona: clic dentro del campo y luego pulsaciones de teclado.

    A diferencia de asignar el valor con setValue()/setText(), esto pasa por
    los mismos validadores que el teclado real. Fue la omisión de este tipo
    de prueba la que dejó pasar el defecto de los campos kW y tanque.
    """
    if not texto.isascii():
        # QTest solo simula teclas ASCII: con "é" o "ñ", Qt aborta el programa entero
        # en lugar de lanzar un error. Mejor un mensaje claro que un cierre misterioso.
        raise ValueError(
            f"escribir_como_usuario solo admite texto ASCII; recibió {texto!r}. "
            "Para tildes o eñes, asigne el texto con setText()."
        )
    widget.setFocus()
    QTest.mouseClick(widget, Qt.MouseButton.LeftButton)
    QTest.keyClicks(widget, texto)
    QApplication.processEvents()
