"""
Campo de texto para números, con vacío = "sin dato".

Ruta: src/presentation/widgets/campo_numerico.py

Reemplaza a QSpinBox / QDoubleSpinBox en los formularios. Esos controles
traían un texto inicial ("—" o "0,00") y rechazaban EN SILENCIO cualquier
tecla que dejara el texto inválido: al hacer clic y escribir "4" junto al
"—", el resultado "—4" no es un número y la tecla se perdía. El usuario
sentía que "el campo no deja escribir" (defecto reportado en la validación
del MVP 1).

Este campo empieza vacío, acepta coma o punto como separador decimal
y solo bloquea lo que de verdad no puede formar un número.
"""

import re

from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import QLineEdit, QWidget


class CampoNumerico(QLineEdit):
    """Campo numérico opcional: decimal (con coma o punto) o entero (con puntos de miles)."""

    def __init__(
        self,
        decimales: int = 2,
        max_digitos: int = 9,
        placeholder: str = "",
        parent: QWidget | None = None,
    ) -> None:
        """
        Args:
            decimales: Máximo de decimales; 0 = número entero.
            max_digitos: Máximo de dígitos de la parte entera.
            placeholder: Texto de ejemplo que se ve cuando el campo está vacío.
        """
        super().__init__(parent)
        self._decimales = decimales
        if decimales == 0:
            # Enteros: se permiten puntos de miles al escribir ("1.200").
            patron = rf"[0-9.]{{0,{max_digitos + max_digitos // 3}}}"
        else:
            # Decimales: dígitos y, opcionalmente, una coma o un punto con decimales.
            patron = rf"[0-9]{{0,{max_digitos}}}([.,][0-9]{{0,{decimales}}})?"
        self.setValidator(QRegularExpressionValidator(patron, self))
        self.setPlaceholderText(placeholder)
        if decimales == 0:
            self.editingFinished.connect(self._formatear_miles)

    # --- API pública ------------------------------------------------------

    def valor(self) -> float | None:
        """Número escrito, o None si el campo está vacío."""
        texto = self.text().strip()
        if self._decimales == 0:
            digitos = re.sub(r"\D", "", texto)
            return float(digitos) if digitos else None
        if not texto or texto in {",", "."}:
            return None
        return float(texto.replace(",", "."))

    def valor_entero(self) -> int | None:
        """Igual que valor(), convertido a entero."""
        numero = self.valor()
        return int(numero) if numero is not None else None

    def set_valor(self, numero: float | None) -> None:
        """Muestra un número en formato colombiano; None deja el campo vacío."""
        if numero is None:
            self.clear()
        elif self._decimales == 0:
            self.setText(f"{int(numero):,}".replace(",", "."))
        else:
            texto = f"{numero:.{self._decimales}f}".rstrip("0").rstrip(".")
            self.setText(texto.replace(".", ","))

    # --- Interno ------------------------------------------------------------

    def _formatear_miles(self) -> None:
        """Al salir del campo: 1200 -> 1.200 (solo en modo entero)."""
        self.set_valor(self.valor())
