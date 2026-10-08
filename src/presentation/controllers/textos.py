"""
Textos de presentación compartidos por los controladores.

Ruta: src/presentation/controllers/textos.py

Antes vivían dentro del controlador del inventario; ahora también los usa
la ficha de la planta. Tenerlos en un solo lugar evita que "PE-005 · Cummins
C50D6" se escriba de dos formas distintas en la aplicación.
"""

from typing import Final

from src.business.models.planta import CambioEstado, Planta, RegistroConsecutivo
from src.shared.formatters import formatear_consecutivo, formatear_entero

FORMATO_FECHA: Final[str] = "%d/%m/%Y"


def describir_planta(planta: Planta) -> str:
    """Ej. "PE-005 · Cummins C50D6"."""
    numero = (
        formatear_consecutivo(planta.numero_consecutivo)
        if planta.numero_consecutivo is not None
        else "Sin número"
    )
    nombre = " ".join(filter(None, [planta.datos.marca, planta.datos.modelo]))
    return f"{numero} · {nombre}"


def filas_historial_estados(cambios: list[CambioEstado]) -> list[tuple[str, ...]]:
    return [
        (
            c.fecha.strftime(FORMATO_FECHA),
            c.estado_anterior.etiqueta if c.estado_anterior else "— (registro)",
            c.estado_nuevo.etiqueta,
            formatear_entero(c.horometro, "h") if c.horometro is not None else "",
            c.motivo or "",
        )
        for c in cambios
    ]


def filas_historial_consecutivos(registros: list[RegistroConsecutivo]) -> list[tuple[str, ...]]:
    return [
        (
            formatear_consecutivo(r.numero),
            r.fecha_asignacion.strftime(FORMATO_FECHA),
            r.fecha_liberacion.strftime(FORMATO_FECHA) if r.fecha_liberacion else "Vigente",
            r.motivo_liberacion or "",
        )
        for r in registros
    ]
