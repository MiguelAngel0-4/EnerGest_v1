"""
Reglas de asignación y reutilización de números consecutivos.

Ruta: src/business/services/consecutivo_service.py

Este servicio NUNCA abre su propia transacción: recibe la unidad de
trabajo de quien lo llama, para participar en la misma "compra".
Así, asignar el número y crear la planta se confirman juntos.
"""

import logging
from datetime import date

from src.business.interfaces.unidad_de_trabajo import IUnidadDeTrabajo

logger = logging.getLogger(__name__)


class ConsecutivoService:
    """Administra el ciclo de vida de los números consecutivos."""

    @staticmethod
    def calcular_menor_libre(en_uso: set[int]) -> int:
        """
        Devuelve el menor entero positivo que no esté en uso.

        Ejemplos: {} -> 1 | {1, 2, 3} -> 4 | {1, 3} -> 2 | {2, 3} -> 1
        """
        candidato = 1
        while candidato in en_uso:
            candidato += 1
        return candidato

    def proponer_para_nueva(self, uow: IUnidadDeTrabajo) -> int:
        """Número que debe recibir una planta recién registrada."""
        return self.calcular_menor_libre(uow.consecutivos.numeros_en_uso())

    def proponer_para_reactivacion(self, uow: IUnidadDeTrabajo, planta_id: int) -> int:
        """
        Número para una planta retirada que vuelve a operar.

        Prioriza su número anterior si sigue libre; si otra planta lo
        tomó, recibe el menor disponible.
        """
        en_uso = uow.consecutivos.numeros_en_uso()
        anterior = uow.consecutivos.ultimo_numero_de(planta_id)
        if anterior is not None and anterior not in en_uso:
            return anterior
        return self.calcular_menor_libre(en_uso)

    def registrar_asignacion(
        self, uow: IUnidadDeTrabajo, planta_id: int, numero: int, fecha: date
    ) -> None:
        """Deja constancia en el historial de que la planta recibe el número."""
        uow.consecutivos.abrir_registro(planta_id, numero, fecha)
        logger.info("Consecutivo %s asignado a la planta id=%s.", numero, planta_id)

    def liberar(self, uow: IUnidadDeTrabajo, planta_id: int, fecha: date, motivo: str) -> None:
        """Cierra el registro vigente de la planta: su número queda disponible."""
        uow.consecutivos.cerrar_registro(planta_id, fecha, motivo)
        logger.info("Consecutivo de la planta id=%s liberado. Motivo: %s", planta_id, motivo)
