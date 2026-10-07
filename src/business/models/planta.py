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
    """
    Tipos de combustible.

    GAS se conserva solo como dato histórico: las plantas registradas antes
    de retirarlo lo mantienen, pero no puede asignarse a ninguna otra.
    """

    DIESEL = "DIESEL"
    GASOLINA = "GASOLINA"
    GAS = "GAS"

    @property
    def etiqueta(self) -> str:
        """Nombre legible para mostrar al usuario."""
        return {"DIESEL": "Diésel", "GASOLINA": "Gasolina", "GAS": "Gas"}[self.value]

    @property
    def vigente(self) -> bool:
        """True si puede elegirse al registrar o editar una planta."""
        return self is not TipoCombustible.GAS


class TipoAceite(StrEnum):
    """Tipos de aceite de motor admitidos (clasificación de viscosidad SAE)."""

    SAE_15W40 = "SAE_15W40"
    SAE_25W60 = "SAE_25W60"

    @property
    def etiqueta(self) -> str:
        """Nombre legible para mostrar al usuario."""
        return {"SAE_15W40": "15W-40", "SAE_25W60": "25W-60"}[self.value]


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
    # Consumibles de mantenimiento (versión 2 del esquema)
    filtro_aceite: str | None = None
    filtro_combustible: str | None = None  # Filtro de combustible / separador de agua
    filtro_agua: str | None = None
    filtro_aire: str | None = None
    cantidad_aceite_gal: float | None = None
    tipo_aceite: TipoAceite | None = None


@dataclass(frozen=True, slots=True)
class Planta:
    """Planta registrada: datos del usuario + campos que controla el sistema."""

    id: int
    numero_consecutivo: int | None
    estado: EstadoPlanta
    datos: DatosPlanta
    fecha_registro: datetime
    # Última lectura conocida: el mayor valor entre el horómetro inicial y las
    # lecturas registradas en los cambios de estado. Lo calcula el repositorio.
    horometro_actual: int


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
    horometro: int | None = None  # Lectura del horómetro al momento del cambio
