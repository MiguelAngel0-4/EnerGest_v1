"""
Estados del ciclo de vida de una planta eléctrica.

Ruta: src/business/models/estado_planta.py

Contiene la máquina de estados aprobada. Es el ÚNICO lugar donde se
definen las transiciones permitidas: si una regla cambia, se cambia aquí.
"""

from enum import StrEnum
from typing import Final


class EstadoPlanta(StrEnum):
    """
    Estados posibles de una planta.

    StrEnum permite comparar directamente con el texto guardado en SQLite:
    EstadoPlanta("VENDIDA") == "VENDIDA"  ->  True
    """

    DISPONIBLE = "DISPONIBLE"
    ALQUILADA = "ALQUILADA"
    EN_MANTENIMIENTO = "EN_MANTENIMIENTO"
    RETIRADA = "RETIRADA"
    VENDIDA = "VENDIDA"
    DADA_DE_BAJA = "DADA_DE_BAJA"

    @property
    def etiqueta(self) -> str:
        """Nombre legible para mostrar al usuario."""
        return _ETIQUETAS[self]

    @property
    def en_operacion(self) -> bool:
        """True si la planta debe tener un número consecutivo asignado."""
        return self not in ESTADOS_FUERA_DE_OPERACION

    @property
    def es_final(self) -> bool:
        """True si desde este estado ya no se puede pasar a ningún otro."""
        return not _TRANSICIONES[self]

    @property
    def requiere_motivo(self) -> bool:
        """True si para ENTRAR a este estado se debe justificar el motivo."""
        return not self.en_operacion

    def destinos_posibles(self) -> frozenset["EstadoPlanta"]:
        """Estados a los que se puede pasar desde este (útil para la UI)."""
        return _TRANSICIONES[self]

    def puede_pasar_a(self, destino: "EstadoPlanta") -> bool:
        """Indica si la transición self -> destino está permitida."""
        return destino in _TRANSICIONES[self]


# Estados que liberan el consecutivo al entrar en ellos.
ESTADOS_FUERA_DE_OPERACION: Final[frozenset[EstadoPlanta]] = frozenset(
    {EstadoPlanta.RETIRADA, EstadoPlanta.VENDIDA, EstadoPlanta.DADA_DE_BAJA}
)

# Tabla de transiciones aprobada: estado actual -> estados destino permitidos.
_TRANSICIONES: Final[dict[EstadoPlanta, frozenset[EstadoPlanta]]] = {
    EstadoPlanta.DISPONIBLE: frozenset(
        {
            EstadoPlanta.ALQUILADA,
            EstadoPlanta.EN_MANTENIMIENTO,
            EstadoPlanta.RETIRADA,
            EstadoPlanta.VENDIDA,
            EstadoPlanta.DADA_DE_BAJA,
        }
    ),
    EstadoPlanta.ALQUILADA: frozenset({EstadoPlanta.DISPONIBLE, EstadoPlanta.EN_MANTENIMIENTO}),
    EstadoPlanta.EN_MANTENIMIENTO: frozenset(
        {EstadoPlanta.DISPONIBLE, EstadoPlanta.DADA_DE_BAJA}
    ),
    EstadoPlanta.RETIRADA: frozenset(
        {EstadoPlanta.DISPONIBLE, EstadoPlanta.VENDIDA, EstadoPlanta.DADA_DE_BAJA}
    ),
    EstadoPlanta.VENDIDA: frozenset(),
    EstadoPlanta.DADA_DE_BAJA: frozenset(),
}

_ETIQUETAS: Final[dict[EstadoPlanta, str]] = {
    EstadoPlanta.DISPONIBLE: "Disponible",
    EstadoPlanta.ALQUILADA: "Alquilada",
    EstadoPlanta.EN_MANTENIMIENTO: "En mantenimiento",
    EstadoPlanta.RETIRADA: "Retirada",
    EstadoPlanta.VENDIDA: "Vendida",
    EstadoPlanta.DADA_DE_BAJA: "Dada de baja",
}
