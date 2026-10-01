"""
Conversiones entre los tipos de Python y los de SQLite.

Ruta: src/infrastructure/repositories/conversiones.py

Son el "intérprete" de la capa de datos: el negocio habla con objetos
date y datetime; SQLite guarda texto ISO ('2026-09-30'). Ningún otro
archivo del sistema debería convertir fechas a texto por su cuenta.
"""

from datetime import date, datetime


def fecha_a_texto(valor: date | None) -> str | None:
    """date(2026, 9, 30) -> '2026-09-30'."""
    return valor.isoformat() if valor is not None else None


def texto_a_fecha(valor: str | None) -> date | None:
    """'2026-09-30' -> date(2026, 9, 30). None se conserva como None."""
    return date.fromisoformat(valor) if valor is not None else None


def texto_a_fecha_obligatoria(valor: str) -> date:
    """Igual que texto_a_fecha, para columnas NOT NULL."""
    return date.fromisoformat(valor)


def texto_a_fecha_hora(valor: str) -> datetime:
    """'2026-09-30 14:25:00' -> datetime(2026, 9, 30, 14, 25)."""
    return datetime.fromisoformat(valor)


def escapar_like(texto: str) -> str:
    """
    Escapa los comodines de LIKE para buscar el texto de forma literal.

    Sin esto, si el usuario busca "50%", el símbolo % actuaría como
    comodín y la búsqueda devolvería resultados inesperados.
    Debe usarse junto con la cláusula ESCAPE '\\' en la consulta.
    """
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
