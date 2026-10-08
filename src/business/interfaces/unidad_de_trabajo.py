"""
Contrato de la Unidad de Trabajo (Unit of Work).

Ruta: src/business/interfaces/unidad_de_trabajo.py

Funciona como un carrito de compras: dentro del bloque "with" se usan
varios repositorios, y al salir todo se confirma junto o se deshace junto.

    with uow_factory() as uow:
        planta_id = uow.plantas.insertar(...)
        uow.consecutivos.abrir_registro(planta_id, ...)
    # Aquí: si no hubo errores, COMMIT. Si hubo, ROLLBACK de todo.
"""

from collections.abc import Callable
from types import TracebackType
from typing import Protocol, Self

from src.business.interfaces.gasto_repository import (
    ICategoriaRepository,
    IFacturaRepository,
    IGastoRepository,
    IProveedorRepository,
)
from src.business.interfaces.mantenimiento_repository import IMantenimientoRepository
from src.business.interfaces.planta_repository import (
    IConsecutivoRepository,
    IHistorialEstadoRepository,
    IPlantaRepository,
)


class IUnidadDeTrabajo(Protocol):
    """Agrupa los repositorios que comparten una misma transacción."""

    plantas: IPlantaRepository
    consecutivos: IConsecutivoRepository
    historial_estados: IHistorialEstadoRepository
    # Módulo de gastos (Actividad 4.1)
    gastos: IGastoRepository
    facturas: IFacturaRepository
    proveedores: IProveedorRepository
    categorias: ICategoriaRepository
    # Módulo de mantenimientos (Actividad 4.2)
    mantenimientos: IMantenimientoRepository

    def __enter__(self) -> Self:
        """Inicia la transacción."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Confirma si no hubo errores; deshace si los hubo. Nunca oculta la excepción."""
        ...


# Fábrica que crea una unidad de trabajo nueva en cada llamada.
FabricaUnidadDeTrabajo = Callable[[], IUnidadDeTrabajo]
