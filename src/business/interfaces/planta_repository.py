"""
Contratos de los repositorios del módulo de plantas.

Ruta: src/business/interfaces/planta_repository.py

Un Protocol describe QUÉ debe saber hacer un repositorio, sin decir CÓMO.
La capa de negocio depende solo de estos contratos; la infraestructura
los cumple con SQLite y las pruebas los cumplen con versiones en memoria.

Regla para quien implemente: ante cualquier falla técnica, lanzar
PersistenciaError (src/business/exceptions.py), nunca errores de sqlite3.
"""

from datetime import date
from typing import Protocol

from src.business.models.estado_planta import EstadoPlanta
from src.business.models.planta import CambioEstado, DatosPlanta, Planta, RegistroConsecutivo


class IPlantaRepository(Protocol):
    """Acceso a la tabla de plantas."""

    def insertar(self, datos: DatosPlanta, numero: int, estado: EstadoPlanta) -> int:
        """Guarda una planta nueva y devuelve su id."""
        ...

    def actualizar_datos(self, planta_id: int, datos: DatosPlanta) -> None:
        """Reemplaza los datos técnicos (no toca estado ni consecutivo)."""
        ...

    def actualizar_estado(
        self, planta_id: int, estado: EstadoPlanta, numero: int | None
    ) -> None:
        """Cambia estado y consecutivo en UNA sola sentencia (lo exige el CHECK)."""
        ...

    def obtener(self, planta_id: int) -> Planta | None:
        """Devuelve la planta o None si no existe."""
        ...

    def listar(
        self, estados: set[EstadoPlanta] | None = None, texto: str | None = None
    ) -> list[Planta]:
        """Lista plantas filtrando por estados y texto (marca, modelo o serie)."""
        ...

    def existe_numero_serie(self, serie: str, excluir_id: int | None = None) -> bool:
        """Indica si otra planta ya usa ese número de serie."""
        ...


class IConsecutivoRepository(Protocol):
    """Acceso al historial de consecutivos."""

    def numeros_en_uso(self) -> set[int]:
        """Números asignados actualmente a plantas en operación."""
        ...

    def abrir_registro(self, planta_id: int, numero: int, fecha: date) -> None:
        """Registra que la planta recibe un número desde la fecha dada."""
        ...

    def cerrar_registro(self, planta_id: int, fecha: date, motivo: str) -> None:
        """Cierra el registro vigente de la planta (libera su número)."""
        ...

    def ultimo_numero_de(self, planta_id: int) -> int | None:
        """Último número que tuvo la planta, o None si nunca tuvo."""
        ...

    def historial_de_planta(self, planta_id: int) -> list[RegistroConsecutivo]:
        """Todos los números que ha tenido una planta, del más antiguo al más reciente."""
        ...

    def historial_de_numero(self, numero: int) -> list[RegistroConsecutivo]:
        """Todas las plantas que han tenido un número, de la más antigua a la más reciente."""
        ...


class IHistorialEstadoRepository(Protocol):
    """Acceso a la línea de tiempo de estados."""

    def registrar(self, cambio: CambioEstado) -> None:
        """Guarda un cambio de estado."""
        ...

    def listar_por_planta(self, planta_id: int) -> list[CambioEstado]:
        """Cambios de una planta en orden cronológico (el último es el más reciente)."""
        ...
