"""
Excepciones de la capa de negocio.

Ruta: src/business/exceptions.py

Todas heredan de NegocioError y sus mensajes están redactados para
mostrarse directamente al usuario en la interfaz.
"""

from src.business.models.estado_planta import EstadoPlanta


class NegocioError(Exception):
    """Error base del negocio."""


class ValidacionError(NegocioError):
    """
    Uno o varios datos no cumplen las reglas.

    Atributos:
        errores: Diccionario {campo: mensaje} con TODOS los errores encontrados,
                 para que el formulario pueda resaltar cada campo a la vez.
    """

    def __init__(self, errores: dict[str, str]) -> None:
        self.errores: dict[str, str] = dict(errores)
        detalle = " ".join(self.errores.values())
        super().__init__(f"Datos inválidos. {detalle}")


class PlantaNoEncontradaError(NegocioError):
    """No existe una planta con el id solicitado."""

    def __init__(self, planta_id: int) -> None:
        self.planta_id = planta_id
        super().__init__(f"No existe una planta con id {planta_id}.")


class TransicionInvalidaError(NegocioError):
    """El cambio de estado solicitado no está permitido."""

    def __init__(self, origen: EstadoPlanta, destino: EstadoPlanta) -> None:
        self.origen = origen
        self.destino = destino
        super().__init__(
            f"No se puede pasar una planta de '{origen.etiqueta}' a '{destino.etiqueta}'."
        )


class PersistenciaError(NegocioError):
    """
    Falla técnica al leer o guardar datos.

    La lanzan los repositorios al traducir errores de la base de datos,
    para que el negocio nunca dependa de excepciones de SQLite.
    """


class DocumentoError(NegocioError):
    """
    No se pudo crear un documento (hoja de vida, reporte).

    La lanza el generador de la infraestructura al traducir errores del
    sistema de archivos, para que la interfaz muestre un mensaje claro.
    """
