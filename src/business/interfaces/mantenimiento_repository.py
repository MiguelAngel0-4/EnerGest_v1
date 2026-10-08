"""
Contrato del repositorio de mantenimientos.

Ruta: src/business/interfaces/mantenimiento_repository.py
"""

from typing import Protocol

from src.business.models.mantenimiento import DatosMantenimiento, Mantenimiento


class IMantenimientoRepository(Protocol):
    def insertar(self, planta_id: int, datos: DatosMantenimiento) -> int: ...

    def obtener(self, mantenimiento_id: int) -> Mantenimiento | None: ...

    def anular(self, mantenimiento_id: int, motivo: str) -> None: ...

    def listar_por_planta(
        self, planta_id: int, incluir_anulados: bool = False
    ) -> list[Mantenimiento]:
        """Del más reciente al más antiguo."""
        ...

    def ultimo_vigente(self, planta_id: int) -> Mantenimiento | None:
        """Último mantenimiento NO anulado de la planta."""
        ...

    def ultimos_por_planta(self) -> dict[int, Mantenimiento]:
        """{planta_id: último mantenimiento NO anulado}, para calcular las alertas."""
        ...

    def tecnicos_registrados(self) -> list[str]:
        """Nombres de técnicos ya usados, para sugerirlos al escribir."""
        ...
