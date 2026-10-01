"""
Modelos de dominio de las plantas eléctricas.

Ruta: src/business/models/planta.py

Todas las clases son inmutables (frozen=True): funcionan como
"fotografías" de los datos. Para cambiar algo se pasa por el servicio,
que devuelve una fotografía nueva. Así ninguna vista puede alterar
el estado o el consecutivo saltándose las reglas.
"""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from src.business.models.estado_planta import EstadoPlanta


class TipoCombustible(StrEnum):
    """Tipos de combustible admitidos."""

    DIESEL = "DIESEL"
    GASOLINA = "GASOLINA"

    @property
    def etiqueta(self) -> str:
        """Nombre legible para mostrar al usuario."""
        return {"DIESEL": "Diésel", "GASOLINA": "Gasolina"}[self.value]


@dataclass(frozen=True, slots=True)
class DatosPlanta:
    """Datos técnicos que diligencia el usuario en el formulario."""

    marca: str
    potencia_kva: float
    modelo: str | None = None
    numero_serie: str | None = None
    potencia_kw: float | None = None
    voltaje: str | None = None
    fases: int | None = None
    tipo_combustible: TipoCombustible | None = None
    capacidad_tanque_gal: float | None = None
    fecha_adquisicion: date | None = None
    valor_compra: int | None = None
    horometro_inicial: int = 0
    observaciones: str | None = None


@dataclass(frozen=True, slots=True)
class Planta:
    """Planta registrada: datos del usuario + campos que controla el sistema."""

    id: int
    numero_consecutivo: int | None
    estado: EstadoPlanta
    datos: DatosPlanta
    fecha_registro: datetime


@dataclass(frozen=True, slots=True)
class RegistroConsecutivo:
    """Periodo durante el cual una planta tuvo un número ("dorsal")."""

    planta_id: int
    numero: int
    fecha_asignacion: date
    fecha_liberacion: date | None = None
    motivo_liberacion: str | None = None

    @property
    def vigente(self) -> bool:
        """True si la planta aún conserva este número."""
        return self.fecha_liberacion is None


@dataclass(frozen=True, slots=True)
class CambioEstado:
    """Un evento en la línea de tiempo de estados de una planta."""

    planta_id: int
    estado_anterior: EstadoPlanta | None
    estado_nuevo: EstadoPlanta
    fecha: date
    motivo: str | None = None
