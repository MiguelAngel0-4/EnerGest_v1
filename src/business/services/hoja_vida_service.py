"""
Caso de uso: generar la hoja de vida técnica de una planta.

Ruta: src/business/services/hoja_vida_service.py

Reúne en un solo objeto (HojaDeVida) la planta, sus historiales y los
datos de la empresa, y se lo entrega al generador de documentos. No sabe
que existe ReportLab ni PDF: depende solo del contrato IGeneradorHojaVida.
"""

import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from src.business.exceptions import PlantaNoEncontradaError
from src.business.interfaces.generador_documentos import IGeneradorHojaVida
from src.business.interfaces.unidad_de_trabajo import FabricaUnidadDeTrabajo
from src.business.models.hoja_vida import DatosEmpresa, HojaDeVida

logger = logging.getLogger(__name__)


class HojaVidaService:
    """Prepara y exporta hojas de vida técnicas."""

    def __init__(
        self,
        uow_factory: FabricaUnidadDeTrabajo,
        generador: IGeneradorHojaVida,
        empresa: Callable[[], DatosEmpresa],
        version_app: str,
        ahora: Callable[[], datetime] = datetime.now,
    ) -> None:
        """
        Args:
            uow_factory: Crea una unidad de trabajo por operación.
            generador: Produce el archivo (PDF con ReportLab en producción).
            empresa: Entrega los datos actuales de la empresa. Es una función y
                     no un valor fijo, para que un cambio en los datos de la
                     empresa se refleje sin reiniciar la aplicación.
            version_app: Versión del programa, para el pie de página.
            ahora: "Reloj inyectable" (fecha fija en las pruebas).
        """
        self._uow_factory = uow_factory
        self._generador = generador
        self._empresa = empresa
        self._version_app = version_app
        self._ahora = ahora

    def preparar(self, planta_id: int) -> HojaDeVida:
        """
        Reúne todo el contenido de la hoja de vida.

        Raises:
            PlantaNoEncontradaError
        """
        with self._uow_factory() as uow:
            planta = uow.plantas.obtener(planta_id)
            if planta is None:
                raise PlantaNoEncontradaError(planta_id)
            cambios = uow.historial_estados.listar_por_planta(planta_id)
            consecutivos = uow.consecutivos.historial_de_planta(planta_id)
            # El repositorio los entrega del más reciente al más antiguo; el documento
            # los muestra en orden cronológico, como los demás historiales.
            mantenimientos = list(reversed(uow.mantenimientos.listar_por_planta(planta_id)))

        return HojaDeVida(
            planta=planta,
            cambios_estado=tuple(cambios),
            consecutivos=tuple(consecutivos),
            empresa=self._empresa(),
            generado_en=self._ahora(),
            version_app=self._version_app,
            mantenimientos=tuple(mantenimientos),
        )

    def exportar(self, planta_id: int, destino: Path) -> Path:
        """
        Genera el documento en la ruta indicada.

        Raises:
            PlantaNoEncontradaError, DocumentoError
        """
        hoja = self.preparar(planta_id)
        ruta = self._generador.generar(hoja, destino)
        logger.info("Hoja de vida de la planta id=%s generada en %s", planta_id, ruta)
        return ruta
