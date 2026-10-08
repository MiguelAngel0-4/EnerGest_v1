"""
Validación de gastos, facturas y proveedores.

Ruta: src/business/validators/gasto_validator.py

Igual que con las plantas: primero se normaliza (espacios, vacíos -> None)
y luego se revisan TODAS las reglas, devolviendo todos los errores juntos.
Las reglas que necesitan consultar la base de datos (saldo de la factura,
duplicados) las verifica el servicio.
"""

from dataclasses import replace
from datetime import date

from src.business.models.gasto import DatosFactura, DatosGasto


def _texto_opcional(valor: str | None) -> str | None:
    if valor is None:
        return None
    return valor.strip() or None


def normalizar_gasto(datos: DatosGasto) -> DatosGasto:
    return replace(
        datos,
        descripcion=(datos.descripcion or "").strip(),
        unidad=_texto_opcional(datos.unidad),
    )


def validar_gasto(datos: DatosGasto, hoy: date) -> dict[str, str]:
    errores: dict[str, str] = {}
    if not datos.descripcion:
        errores["descripcion"] = "La descripción es obligatoria."
    if datos.valor_total <= 0:
        errores["valor_total"] = "El valor debe ser mayor que 0."
    if datos.cantidad <= 0:
        errores["cantidad"] = "La cantidad debe ser mayor que 0."
    if datos.fecha > hoy:
        errores["fecha"] = "La fecha del gasto no puede ser futura."
    return errores


def normalizar_factura(datos: DatosFactura) -> DatosFactura:
    return replace(
        datos,
        numero_factura=(datos.numero_factura or "").strip(),
        observaciones=_texto_opcional(datos.observaciones),
    )


def validar_factura(datos: DatosFactura, hoy: date) -> dict[str, str]:
    errores: dict[str, str] = {}
    if not datos.numero_factura:
        errores["numero_factura"] = "El número de la factura es obligatorio."
    if datos.valor_total <= 0:
        errores["valor_total"] = "El valor total debe ser mayor que 0."
    if datos.fecha_factura > hoy:
        errores["fecha_factura"] = "La fecha de la factura no puede ser futura."
    return errores
