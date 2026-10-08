"""
Datos de la empresa guardados en un archivo JSON editable.

Ruta: src/infrastructure/repositories/empresa_json_repository.py

El archivo vive en la carpeta de datos (data/empresa.json), junto a la
base de datos. La primera vez se crea copiando la plantilla de
resources/templates/empresa.json. Así los datos se ajustan en cada
instalación sin tocar el código ni recompilar el ejecutable.

Si el archivo se daña (por ejemplo, al borrar una coma por error), los
documentos se siguen generando con un nombre genérico y el problema queda
en el log: un error de configuración nunca debe impedir trabajar.
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Any, Final

from src.business.models.hoja_vida import DatosEmpresa

logger = logging.getLogger(__name__)

NOMBRE_POR_DEFECTO: Final[str] = "Empresa sin configurar"


class EmpresaJsonRepository:
    """Lee los datos de la empresa desde un archivo JSON."""

    def __init__(self, ruta: Path, plantilla: Path | None = None) -> None:
        """
        Args:
            ruta: Ubicación del archivo, normalmente data/empresa.json.
            plantilla: Archivo que se copia si el JSON aún no existe.
        """
        self._ruta = ruta
        self._plantilla = plantilla

    @property
    def ruta(self) -> Path:
        return self._ruta

    def obtener(self) -> DatosEmpresa:
        """
        Lee el archivo en cada llamada: si alguien lo edita, el siguiente
        documento ya refleja el cambio, sin reiniciar la aplicación.
        """
        self._crear_si_no_existe()
        try:
            contenido: Any = json.loads(self._ruta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("No se pudo leer %s (%s); se usan datos genéricos.", self._ruta, exc)
            return DatosEmpresa(NOMBRE_POR_DEFECTO)
        if not isinstance(contenido, dict):
            logger.warning("%s no tiene el formato esperado; se usan datos genéricos.", self._ruta)
            return DatosEmpresa(NOMBRE_POR_DEFECTO)

        return DatosEmpresa(
            nombre=_texto(contenido.get("nombre")) or NOMBRE_POR_DEFECTO,
            nit=_texto(contenido.get("nit")),
            telefono=_texto(contenido.get("telefono")),
            direccion=_texto(contenido.get("direccion")),
            ruta_logo=self._ruta_logo(_texto(contenido.get("logo"))),
        )

    def _crear_si_no_existe(self) -> None:
        if self._ruta.exists():
            return
        try:
            self._ruta.parent.mkdir(parents=True, exist_ok=True)
            if self._plantilla is not None and self._plantilla.is_file():
                shutil.copyfile(self._plantilla, self._ruta)
            else:
                contenido = {"nombre": NOMBRE_POR_DEFECTO, "nit": "", "telefono": "",
                             "direccion": "", "logo": "logo_empresa.png"}
                self._ruta.write_text(
                    json.dumps(contenido, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            logger.info("Se creó el archivo de datos de la empresa: %s", self._ruta)
        except OSError:
            logger.exception("No se pudo crear %s", self._ruta)

    def _ruta_logo(self, nombre: str | None) -> Path | None:
        """El logo puede ser un nombre (se busca junto al JSON) o una ruta completa."""
        if not nombre:
            return None
        ruta = Path(nombre)
        return ruta if ruta.is_absolute() else self._ruta.parent / ruta


def _texto(valor: Any) -> str | None:
    """Convierte a texto limpio; vacío o ausente -> None."""
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None
