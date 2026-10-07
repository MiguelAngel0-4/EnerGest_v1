"""
Traducción entre los valores del formulario y el modelo DatosPlanta.

Ruta: src/presentation/controllers/planta_form_mapper.py

El formulario (vista pura) habla en diccionarios con tipos simples;
el servicio habla en DatosPlanta. Este módulo es el puente entre ambos.
Al no depender de Qt, se prueba con pytest como cualquier función.
"""

from dataclasses import fields
from typing import Any

from src.business.models.planta import DatosPlanta, TipoAceite, TipoCombustible


def datos_a_valores(datos: DatosPlanta) -> dict[str, Any]:
    """DatosPlanta -> diccionario para llenar el formulario (modo edición)."""
    valores = {campo.name: getattr(datos, campo.name) for campo in fields(datos)}
    valores["tipo_combustible"] = datos.tipo_combustible.value if datos.tipo_combustible else None
    valores["tipo_aceite"] = datos.tipo_aceite.value if datos.tipo_aceite else None
    return valores


def valores_a_datos(valores: dict[str, Any]) -> DatosPlanta:
    """Diccionario del formulario -> DatosPlanta (la limpieza y validación las hace el servicio)."""
    combustible = valores.get("tipo_combustible")
    aceite = valores.get("tipo_aceite")
    return DatosPlanta(
        marca=str(valores.get("marca") or ""),
        potencia_kva=float(valores.get("potencia_kva") or 0),
        modelo=valores.get("modelo"),
        numero_serie=valores.get("numero_serie"),
        potencia_kw=valores.get("potencia_kw"),
        voltaje=valores.get("voltaje"),
        fases=valores.get("fases"),
        tipo_combustible=TipoCombustible(combustible) if combustible else None,
        capacidad_tanque_gal=valores.get("capacidad_tanque_gal"),
        fecha_adquisicion=valores.get("fecha_adquisicion"),
        valor_compra=valores.get("valor_compra"),
        horometro_inicial=int(valores.get("horometro_inicial") or 0),
        observaciones=valores.get("observaciones"),
        filtro_aceite=valores.get("filtro_aceite"),
        filtro_combustible=valores.get("filtro_combustible"),
        filtro_agua=valores.get("filtro_agua"),
        filtro_aire=valores.get("filtro_aire"),
        cantidad_aceite_gal=valores.get("cantidad_aceite_gal"),
        tipo_aceite=TipoAceite(aceite) if aceite else None,
    )
