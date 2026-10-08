"""
Validación de mantenimientos y de sus líneas de insumos.

Ruta: src/business/validators/mantenimiento_validator.py
"""

from dataclasses import replace
from datetime import date

from src.business.models.mantenimiento import DatosMantenimiento, LineaInsumo


def normalizar_mantenimiento(datos: DatosMantenimiento) -> DatosMantenimiento:
    return replace(
        datos,
        descripcion=(datos.descripcion or "").strip(),
        tecnico=(datos.tecnico or "").strip() or None,
    )


def normalizar_insumo(linea: LineaInsumo) -> LineaInsumo:
    return replace(
        linea,
        descripcion=(linea.descripcion or "").strip(),
        unidad=(linea.unidad or "").strip() or None,
    )


def validar_mantenimiento(datos: DatosMantenimiento, hoy: date) -> dict[str, str]:
    errores: dict[str, str] = {}
    if not datos.descripcion:
        errores["descripcion"] = "Describa el trabajo realizado."
    if datos.horometro < 0:
        errores["horometro"] = "La lectura del horómetro no puede ser negativa."
    if datos.fecha > hoy:
        errores["fecha"] = "La fecha del mantenimiento no puede ser futura."
    if datos.proxima_fecha is not None and datos.proxima_fecha <= datos.fecha:
        errores["proxima_fecha"] = "El próximo mantenimiento debe programarse después de este."
    if datos.proximo_horometro is not None and datos.proximo_horometro <= datos.horometro:
        errores["proximo_horometro"] = (
            "Las horas del próximo mantenimiento deben superar la lectura actual."
        )
    return errores


def validar_insumos(lineas: list[LineaInsumo]) -> str | None:
    """
    Revisa todas las líneas y devuelve UN mensaje que las nombra por número,
    o None si todas son válidas. Ej.: "Línea 2: el valor debe ser mayor que 0."
    """
    problemas: list[str] = []
    for numero, linea in enumerate(lineas, start=1):
        if not linea.descripcion:
            problemas.append(f"Línea {numero}: falta la descripción.")
        if linea.valor_total <= 0:
            problemas.append(f"Línea {numero}: el valor debe ser mayor que 0.")
        if linea.cantidad <= 0:
            problemas.append(f"Línea {numero}: la cantidad debe ser mayor que 0.")
    return " ".join(problemas) or None
