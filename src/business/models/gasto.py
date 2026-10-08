"""
Modelos de dominio de los gastos por planta.

Ruta: src/business/models/gasto.py

Una factura de proveedor es como el ticket de un supermercado compartido
entre compañeros de apartamento: el ticket es uno solo, pero cada producto
se asigna a quien lo consumió. Aquí, cada gasto se asigna a una planta y
puede (o no) estar respaldado por una factura.

Todos los valores de dinero son enteros en pesos colombianos.
"""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class Proveedor:
    """Empresa o persona a la que se le compra."""

    id: int
    nombre: str
    nit: str | None = None
    telefono: str | None = None
    activo: bool = True


@dataclass(frozen=True, slots=True)
class CategoriaGasto:
    """Clasificación del gasto: Filtros, Repuestos, Mano de obra..."""

    id: int
    nombre: str
    activo: bool = True


@dataclass(frozen=True, slots=True)
class DatosFactura:
    """Lo que el usuario diligencia al registrar una factura."""

    proveedor_id: int
    numero_factura: str
    fecha_factura: date
    valor_total: int
    observaciones: str | None = None


@dataclass(frozen=True, slots=True)
class FacturaProveedor:
    """
    Factura registrada.

    valor_asignado es la suma de los gastos NO anulados que la usan. Lo calcula
    el repositorio en la consulta: no se guarda duplicado, para que nunca
    pueda quedar desactualizado.
    """

    id: int
    datos: DatosFactura
    proveedor_nombre: str
    valor_asignado: int

    @property
    def saldo_por_asignar(self) -> int:
        """Parte de la factura que aún no se ha asignado a ninguna planta."""
        return self.datos.valor_total - self.valor_asignado


@dataclass(frozen=True, slots=True)
class DatosGasto:
    """Lo que el usuario diligencia al registrar un gasto."""

    categoria_id: int
    fecha: date
    descripcion: str
    valor_total: int
    cantidad: float = 1.0
    unidad: str | None = None
    factura_id: int | None = None  # None = gasto sin soporte (compra informal)


@dataclass(frozen=True, slots=True)
class Gasto:
    """Gasto registrado: datos del usuario + campos que controla el sistema."""

    id: int
    planta_id: int
    datos: DatosGasto
    mantenimiento_id: int | None
    anulado: bool
    motivo_anulacion: str | None
    fecha_registro: datetime


@dataclass(frozen=True, slots=True)
class GastoDetalle:
    """Gasto con los nombres ya resueltos, listo para mostrarse en una tabla."""

    gasto: Gasto
    categoria: str
    numero_factura: str | None
    proveedor: str | None
    mantenimiento_fecha: date | None = None  # Si el gasto nació de un mantenimiento

    @property
    def tiene_soporte(self) -> bool:
        return self.gasto.datos.factura_id is not None


@dataclass(frozen=True, slots=True)
class ResumenGastos:
    """Totales de los gastos vigentes (no anulados) de una planta."""

    total: int
    cantidad: int
    sin_soporte: int  # Valor total de los gastos sin factura
    por_categoria: tuple[tuple[str, int], ...]  # (categoría, total), de mayor a menor
