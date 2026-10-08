"""
Contratos de los repositorios del módulo de gastos.

Ruta: src/business/interfaces/gasto_repository.py
"""

from typing import Protocol

from src.business.models.gasto import (
    CategoriaGasto,
    DatosFactura,
    DatosGasto,
    FacturaProveedor,
    Gasto,
    GastoDetalle,
    Proveedor,
    ResumenGastos,
)


class IGastoRepository(Protocol):
    """Acceso a la tabla de gastos."""

    def insertar(
        self, planta_id: int, datos: DatosGasto, mantenimiento_id: int | None = None
    ) -> int: ...

    def obtener(self, gasto_id: int) -> Gasto | None: ...

    def anular(self, gasto_id: int, motivo: str) -> None: ...

    def anular_por_mantenimiento(self, mantenimiento_id: int, motivo: str) -> None:
        """Anula todos los gastos vigentes que nacieron de un mantenimiento."""
        ...

    def listar_por_planta(
        self, planta_id: int, incluir_anulados: bool = False
    ) -> list[GastoDetalle]:
        """Del más reciente al más antiguo."""
        ...

    def resumen_por_planta(self, planta_id: int) -> ResumenGastos:
        """Totales de los gastos NO anulados."""
        ...


class IFacturaRepository(Protocol):
    """Acceso a las facturas de proveedor (con su valor asignado calculado)."""

    def insertar(self, datos: DatosFactura) -> int: ...

    def obtener(self, factura_id: int) -> FacturaProveedor | None: ...

    def existe_numero(self, proveedor_id: int, numero: str) -> bool:
        """Sin distinguir mayúsculas: "fe-001" y "FE-001" son la misma factura."""
        ...

    def listar_con_saldo(self, texto: str | None = None) -> list[FacturaProveedor]:
        """Facturas con saldo por asignar, filtradas por número o proveedor."""
        ...


class IProveedorRepository(Protocol):
    """Acceso a los proveedores."""

    def insertar(self, nombre: str, nit: str | None, telefono: str | None) -> int: ...

    def obtener(self, proveedor_id: int) -> Proveedor | None: ...

    def listar(self) -> list[Proveedor]:
        """Proveedores activos, en orden alfabético."""
        ...

    def existe_nombre(self, nombre: str) -> bool: ...

    def existe_nit(self, nit: str) -> bool: ...


class ICategoriaRepository(Protocol):
    """Acceso al catálogo de categorías de gasto."""

    def obtener(self, categoria_id: int) -> CategoriaGasto | None: ...

    def listar(self) -> list[CategoriaGasto]:
        """Categorías activas, en el orden en que se crearon."""
        ...
