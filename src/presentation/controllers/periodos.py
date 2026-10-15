"""
Conversión de la opción elegida en el selector a un Periodo concreto.

Ruta: src/presentation/controllers/periodos.py

La comparten la ficha (pestaña Balance) y los Reportes financieros: así
"Año actual" significa exactamente lo mismo en ambas pantallas.
"""

from datetime import date

from src.business.models.rentabilidad import Periodo
from src.business.services.rentabilidad_service import RentabilidadService


def periodo_desde_seleccion(
    clave: str,
    desde: date,
    hasta: date,
    rentabilidad: RentabilidadService,
    hoy: date | None = None,
) -> Periodo:
    hoy = hoy or date.today()
    if clave == "ANIO":
        return Periodo(date(hoy.year, 1, 1), hoy)
    if clave == "RECIENTE":
        return rentabilidad.periodo_reciente()
    if clave == "RANGO":
        return Periodo(min(desde, hasta), max(desde, hasta))  # Tolera fechas invertidas
    return Periodo()
