"""
Modelos del módulo comercial: clientes, contratos de alquiler, ventas e ingresos.

Ruta: src/business/models/comercial.py

Como en el arriendo de un apartamento: el CONTRATO dice cuánto se cobra y
cada cuánto; los INGRESOS son el dinero que efectivamente llega.
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class ModalidadAlquiler(StrEnum):
    DIA = "DIA"
    MES = "MES"

    @property
    def etiqueta(self) -> str:
        return {"DIA": "Por día", "MES": "Por mes"}[self.value]


class TipoIngreso(StrEnum):
    ALQUILER = "ALQUILER"
    VENTA = "VENTA"
    OTRO = "OTRO"

    @property
    def etiqueta(self) -> str:
        return {"ALQUILER": "Alquiler", "VENTA": "Venta", "OTRO": "Otro"}[self.value]


@dataclass(frozen=True, slots=True)
class Cliente:
    id: int
    nombre: str
    documento: str | None = None  # NIT o cédula
    telefono: str | None = None
    activo: bool = True


@dataclass(frozen=True, slots=True)
class DatosContrato:
    """Condiciones pactadas que diligencia el usuario al alquilar."""

    cliente_id: int
    modalidad: ModalidadAlquiler
    tarifa: int  # Pesos por día o por mes, según la modalidad
    observaciones: str | None = None


@dataclass(frozen=True, slots=True)
class Alquiler:
    """
    Contrato registrado. cobrado y horas_uso los calcula el repositorio:
    - cobrado: suma de sus ingresos NO anulados.
    - horas_uso: lectura de regreso - lectura de salida (None si falta alguna).
    """

    id: int
    planta_id: int
    cliente_id: int
    cliente_nombre: str
    fecha_inicio: date
    fecha_fin: date | None
    modalidad: ModalidadAlquiler
    tarifa: int
    valor_liquidado: int | None
    observaciones: str | None
    cobrado: int
    horas_uso: int | None

    @property
    def activo(self) -> bool:
        return self.fecha_fin is None

    @property
    def saldo(self) -> int | None:
        """Lo que falta por cobrar de un contrato cerrado (None si sigue activo)."""
        return None if self.valor_liquidado is None else self.valor_liquidado - self.cobrado


@dataclass(frozen=True, slots=True)
class Liquidacion:
    """Resultado del cálculo: meses completos, días cobrados y valor sugerido."""

    meses: int
    dias: int
    valor: int


@dataclass(frozen=True, slots=True)
class DatosIngreso:
    """Un cobro: fecha, descripción, valor y documento opcional (factura o cuenta de cobro)."""

    fecha: date
    descripcion: str
    valor: int
    numero_documento: str | None = None


@dataclass(frozen=True, slots=True)
class DatosVenta:
    cliente_id: int
    valor: int
    numero_documento: str | None = None


@dataclass(frozen=True, slots=True)
class Ingreso:
    id: int
    planta_id: int
    tipo: TipoIngreso
    alquiler_id: int | None
    cliente_id: int | None
    cliente_nombre: str | None
    datos: DatosIngreso
    anulado: bool
    motivo_anulacion: str | None
