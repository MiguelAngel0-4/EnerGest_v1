"""
Modelos de dominio de los mantenimientos.

Ruta: src/business/models/mantenimiento.py

Un mantenimiento funciona como el sticker del cambio de aceite de un carro:
registra lo que se hizo (con la lectura del horómetro) y deja programado el
siguiente, por fecha, por horas o por ambas, "lo que ocurra primero".
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from src.business.models.planta import Planta


class TipoMantenimiento(StrEnum):
    PREVENTIVO = "PREVENTIVO"
    CORRECTIVO = "CORRECTIVO"

    @property
    def etiqueta(self) -> str:
        return {"PREVENTIVO": "Preventivo", "CORRECTIVO": "Correctivo"}[self.value]


@dataclass(frozen=True, slots=True)
class DatosMantenimiento:
    """Lo que el usuario diligencia en el formulario."""

    fecha: date
    tipo: TipoMantenimiento
    horometro: int  # Obligatorio: la empresa lee el horómetro en cada mantenimiento
    descripcion: str
    tecnico: str | None = None
    proxima_fecha: date | None = None
    proximo_horometro: int | None = None


@dataclass(frozen=True, slots=True)
class LineaInsumo:
    """Un insumo o servicio del mantenimiento; se guarda como gasto de la planta."""

    categoria_id: int
    descripcion: str
    valor_total: int
    cantidad: float = 1.0
    unidad: str | None = None


@dataclass(frozen=True, slots=True)
class Mantenimiento:
    """
    Mantenimiento registrado.

    costo_total es la suma de sus gastos NO anulados; lo calcula el repositorio.
    """

    id: int
    planta_id: int
    datos: DatosMantenimiento
    anulado: bool
    motivo_anulacion: str | None
    costo_total: int

    @property
    def tiene_programacion(self) -> bool:
        return self.datos.proxima_fecha is not None or self.datos.proximo_horometro is not None


class NivelAlerta(StrEnum):
    VENCIDO = "VENCIDO"
    PROXIMO = "PROXIMO"

    @property
    def etiqueta(self) -> str:
        return {"VENCIDO": "Vencido", "PROXIMO": "Próximo"}[self.value]


@dataclass(frozen=True, slots=True)
class AlertaMantenimiento:
    """
    Planta cuyo próximo mantenimiento ya venció o está cerca.

    dias_restantes y horas_restantes son negativos si ya se pasaron, y None si
    el mantenimiento no se programó por ese criterio.
    """

    planta: Planta
    nivel: NivelAlerta
    proxima_fecha: date | None
    proximo_horometro: int | None
    dias_restantes: int | None
    horas_restantes: int | None
