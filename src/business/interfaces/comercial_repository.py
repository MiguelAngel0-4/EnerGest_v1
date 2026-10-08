"""
Contratos de los repositorios del módulo comercial.

Ruta: src/business/interfaces/comercial_repository.py
"""

from datetime import date
from typing import Protocol

from src.business.models.comercial import (
    Alquiler,
    Cliente,
    DatosContrato,
    DatosIngreso,
    Ingreso,
    TipoIngreso,
)


class IClienteRepository(Protocol):
    def insertar(self, nombre: str, documento: str | None, telefono: str | None) -> int: ...
    def obtener(self, cliente_id: int) -> Cliente | None: ...
    def listar(self) -> list[Cliente]: ...
    def existe_nombre(self, nombre: str) -> bool: ...
    def existe_documento(self, documento: str) -> bool: ...


class IAlquilerRepository(Protocol):
    def insertar(self, planta_id: int, contrato: DatosContrato, fecha_inicio: date) -> int: ...
    def obtener(self, alquiler_id: int) -> Alquiler | None: ...
    def activo_de(self, planta_id: int) -> Alquiler | None: ...
    def cerrar(self, alquiler_id: int, fecha_fin: date, valor_liquidado: int) -> None: ...
    def actualizar_condiciones(self, alquiler_id: int, contrato: DatosContrato) -> None: ...

    def listar_por_planta(self, planta_id: int) -> list[Alquiler]:
        """Del más reciente al más antiguo."""
        ...

    def clientes_actuales(self) -> dict[int, str]:
        """{planta_id: nombre del cliente} de los contratos activos."""
        ...


class IIngresoRepository(Protocol):
    def insertar(
        self,
        planta_id: int,
        tipo: TipoIngreso,
        datos: DatosIngreso,
        alquiler_id: int | None = None,
        cliente_id: int | None = None,
    ) -> int: ...
    def obtener(self, ingreso_id: int) -> Ingreso | None: ...
    def anular(self, ingreso_id: int, motivo: str) -> None: ...

    def listar_por_planta(self, planta_id: int, incluir_anulados: bool = False) -> list[Ingreso]:
        """Del más reciente al más antiguo."""
        ...
