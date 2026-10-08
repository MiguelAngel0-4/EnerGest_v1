"""
Contrato de los generadores de documentos.

Ruta: src/business/interfaces/generador_documentos.py

La capa de negocio sabe QUÉ documento necesita; la infraestructura decide
CÓMO producirlo (hoy con ReportLab en PDF; mañana podría ser otro formato
sin tocar el servicio).
"""

from pathlib import Path
from typing import Protocol

from src.business.models.hoja_vida import HojaDeVida


class IGeneradorHojaVida(Protocol):
    """Convierte una HojaDeVida en un archivo."""

    def generar(self, hoja: HojaDeVida, destino: Path) -> Path:
        """
        Crea el documento en la ruta indicada y la devuelve.

        Raises:
            DocumentoError: Si el archivo no se pudo escribir (por ejemplo, porque
                está abierto en otro programa o la carpeta no permite escritura).
        """
        ...
