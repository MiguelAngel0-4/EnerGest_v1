"""
Validación de los datos técnicos de una planta.

Ruta: src/business/validators/planta_validator.py

Dos pasos, siempre en este orden:
1. normalizar_datos: limpia espacios y convierte textos vacíos en None.
2. validar_datos: revisa TODAS las reglas y devuelve todos los errores juntos.

Estas funciones no acceden a la base de datos; la unicidad del número
de serie la verifica el servicio porque requiere consultar al repositorio.
"""

from dataclasses import replace
from datetime import date
from typing import Final

from src.business.models.planta import DatosPlanta

FASES_VALIDAS: Final[frozenset[int]] = frozenset({1, 3})


def _texto_opcional(valor: str | None) -> str | None:
    """Quita espacios y convierte "" en None."""
    if valor is None:
        return None
    limpio = valor.strip()
    return limpio or None


def normalizar_datos(datos: DatosPlanta) -> DatosPlanta:
    """
    Devuelve una copia limpia de los datos.

    Importante: un número de serie "" debe convertirse en None. Si se
    guardara como texto vacío, la restricción UNIQUE impediría registrar
    una segunda planta sin serie.
    """
    return replace(
        datos,
        marca=(datos.marca or "").strip(),
        modelo=_texto_opcional(datos.modelo),
        numero_serie=_texto_opcional(datos.numero_serie),
        voltaje=_texto_opcional(datos.voltaje),
        observaciones=_texto_opcional(datos.observaciones),
    )


def validar_datos(datos: DatosPlanta, hoy: date) -> dict[str, str]:
    """
    Revisa las reglas de negocio de los datos técnicos.

    Args:
        datos: Datos ya normalizados.
        hoy: Fecha de referencia (se inyecta para poder probar con fechas fijas).

    Returns:
        Diccionario {campo: mensaje}. Vacío si todo es válido.
    """
    errores: dict[str, str] = {}

    if not datos.marca:
        errores["marca"] = "La marca es obligatoria."

    if datos.potencia_kva <= 0:
        errores["potencia_kva"] = "La potencia en kVA debe ser mayor que 0."

    if datos.potencia_kw is not None:
        if datos.potencia_kw <= 0:
            errores["potencia_kw"] = "La potencia en kW debe ser mayor que 0."
        elif datos.potencia_kva > 0 and datos.potencia_kw > datos.potencia_kva:
            # El factor de potencia nunca supera 1, así que kW <= kVA.
            errores["potencia_kw"] = "La potencia en kW no puede superar la potencia en kVA."

    if datos.fases is not None and datos.fases not in FASES_VALIDAS:
        errores["fases"] = "Las fases solo pueden ser 1 (monofásica) o 3 (trifásica)."

    if datos.capacidad_tanque_gal is not None and datos.capacidad_tanque_gal <= 0:
        errores["capacidad_tanque_gal"] = "La capacidad del tanque debe ser mayor que 0."

    if datos.fecha_adquisicion is not None and datos.fecha_adquisicion > hoy:
        errores["fecha_adquisicion"] = "La fecha de adquisición no puede ser futura."

    if datos.valor_compra is not None and datos.valor_compra < 0:
        errores["valor_compra"] = "El valor de compra no puede ser negativo."

    if datos.horometro_inicial < 0:
        errores["horometro_inicial"] = "El horómetro inicial no puede ser negativo."

    return errores
