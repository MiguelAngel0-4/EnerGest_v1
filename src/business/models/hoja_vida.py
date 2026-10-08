"""
Contenido de la hoja de vida técnica de una planta.

Ruta: src/business/models/hoja_vida.py

Es el "QUÉ" del documento: todos los datos que deben aparecer, sin ningún
formato. El "CÓMO" (PDF, colores, tablas) lo decide el generador de la
capa de infraestructura. Como un chef que decide qué va en el plato,
mientras la vajilla define cómo se presenta.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.business.models.mantenimiento import Mantenimiento
from src.business.models.planta import CambioEstado, Planta, RegistroConsecutivo


@dataclass(frozen=True, slots=True)
class DatosEmpresa:
    """Datos de la empresa para el encabezado de los documentos."""

    nombre: str
    nit: str | None = None
    telefono: str | None = None
    direccion: str | None = None
    ruta_logo: Path | None = None


@dataclass(frozen=True, slots=True)
class HojaDeVida:
    """Fotografía completa de una planta en el momento de generar el documento."""

    planta: Planta
    cambios_estado: tuple[CambioEstado, ...]
    consecutivos: tuple[RegistroConsecutivo, ...]
    empresa: DatosEmpresa
    generado_en: datetime
    version_app: str
    # Mantenimientos vigentes, del más antiguo al más reciente (Actividad 4.2)
    mantenimientos: tuple[Mantenimiento, ...] = ()

    @property
    def ultimo_numero(self) -> int | None:
        """Número vigente o, si ya no tiene, el último que tuvo (para plantas vendidas)."""
        if self.planta.numero_consecutivo is not None:
            return self.planta.numero_consecutivo
        return self.consecutivos[-1].numero if self.consecutivos else None
