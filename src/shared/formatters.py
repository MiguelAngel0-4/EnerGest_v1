"""
Formateo de valores para mostrar al usuario.

Ruta: src/shared/formatters.py

La base de datos guarda valores "crudos" (7, 1250000); aquí se
convierten a su forma visible ("PE-007", "$ 1.250.000").
"""

from src.config import settings

SIN_VALOR: str = "—"


def formatear_consecutivo(numero: int | None) -> str:
    """7 -> "PE-007". None (planta fuera de operación) -> "—"."""
    if numero is None:
        return SIN_VALOR
    return f"{settings.CONSECUTIVO_PREFIJO}{numero:0{settings.CONSECUTIVO_DIGITOS}d}"


def formatear_moneda(valor: int | None) -> str:
    """1250000 -> "$ 1.250.000" (formato colombiano, sin centavos)."""
    if valor is None:
        return SIN_VALOR
    signo = "-" if valor < 0 else ""
    return f"{signo}$ {abs(valor):,}".replace(",", ".")
