"""
Contrato del repositorio de consultas de reportes (solo lectura).

Ruta: src/business/interfaces/reporte_repository.py

Los demás repositorios leen y escriben su propia tabla, como la caja
registradora de una tienda. Este solo LEE y CRUZA todas las tablas, como el
informe contable de fin de mes: resume miles de movimientos en pocas cifras.
"""

from datetime import date
from typing import Protocol

from src.business.models.rentabilidad import MesFinanciero, Movimiento, TotalesPlanta


class IReporteRepository(Protocol):
    def totales_por_planta(
        self, desde: date | None = None, hasta: date | None = None
    ) -> dict[int, TotalesPlanta]:
        """{planta_id: totales} de ingresos y gastos vigentes en el período."""
        ...

    def gastos_por_categoria(
        self, planta_id: int, desde: date | None = None, hasta: date | None = None
    ) -> list[tuple[str, int]]:
        """(categoría, total) de mayor a menor."""
        ...

    def meses(
        self, desde: date | None = None, hasta: date | None = None
    ) -> list[MesFinanciero]:
        """Ingresos y gastos por mes ("AAAA-MM"), solo los meses con movimientos."""
        ...

    def horas_uso_alquiler(
        self, planta_id: int, desde: date | None = None, hasta: date | None = None
    ) -> int:
        """Horas de uso de los alquileres que empezaron en el período."""
        ...

    def saldo_por_cobrar(self, planta_id: int | None = None) -> int:
        """Saldo pendiente de los contratos cerrados (de una planta o de todas)."""
        ...

    def movimientos(
        self, desde: date | None = None, hasta: date | None = None
    ) -> list[Movimiento]:
        """Detalle de ingresos y gastos vigentes, por fecha."""
        ...
