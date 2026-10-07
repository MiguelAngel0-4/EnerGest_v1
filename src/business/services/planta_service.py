"""
Casos de uso del módulo de plantas eléctricas.

Ruta: src/business/services/planta_service.py

Es el "chef" de la cocina: recibe pedidos de los controladores,
aplica las reglas de negocio y coordina los repositorios a través de
la unidad de trabajo. No sabe que existen SQLite ni PySide6.
"""

import logging
from collections.abc import Callable
from datetime import date

from src.business.exceptions import (
    PlantaNoEncontradaError,
    TransicionInvalidaError,
    ValidacionError,
)
from src.business.interfaces.unidad_de_trabajo import FabricaUnidadDeTrabajo, IUnidadDeTrabajo
from src.business.models.estado_planta import EstadoPlanta
from src.business.models.planta import (
    CambioEstado,
    DatosPlanta,
    Planta,
    RegistroConsecutivo,
    TipoCombustible,
)
from src.business.services.consecutivo_service import ConsecutivoService
from src.business.validators.planta_validator import normalizar_datos, validar_datos

logger = logging.getLogger(__name__)

MOTIVO_REGISTRO_INICIAL = "Registro inicial"


class PlantaService:
    """Orquesta el registro, edición, cambios de estado y consultas de plantas."""

    def __init__(
        self,
        uow_factory: FabricaUnidadDeTrabajo,
        consecutivos: ConsecutivoService,
        hoy: Callable[[], date] = date.today,
    ) -> None:
        """
        Args:
            uow_factory: Crea una unidad de trabajo nueva por operación.
            consecutivos: Servicio de reglas de consecutivos.
            hoy: "Reloj inyectable". En producción es date.today;
                 en pruebas se reemplaza por una fecha fija.
        """
        self._uow_factory = uow_factory
        self._consecutivos = consecutivos
        self._hoy = hoy

    # ------------------------------------------------------------------ #
    # Comandos (modifican datos)
    # ------------------------------------------------------------------ #

    def registrar(self, datos: DatosPlanta) -> Planta:
        """
        Registra una planta nueva en estado DISPONIBLE con el menor número libre.

        Raises:
            ValidacionError: Si los datos no cumplen las reglas.
        """
        hoy = self._hoy()
        datos = self._normalizar_y_validar(datos, hoy)

        self._verificar_combustible_vigente(datos, combustible_anterior=None)

        with self._uow_factory() as uow:
            self._verificar_serie_unica(uow, datos.numero_serie, excluir_id=None)

            # Orden obligatorio: primero se calcula el número, luego se crea la
            # planta (el CHECK exige que nazca con número) y por último se
            # registra el historial (la llave foránea exige que la planta exista).
            numero = self._consecutivos.proponer_para_nueva(uow)
            planta_id = uow.plantas.insertar(datos, numero, EstadoPlanta.DISPONIBLE)
            self._consecutivos.registrar_asignacion(uow, planta_id, numero, hoy)
            uow.historial_estados.registrar(
                CambioEstado(
                    planta_id=planta_id,
                    estado_anterior=None,
                    estado_nuevo=EstadoPlanta.DISPONIBLE,
                    fecha=hoy,
                    motivo=MOTIVO_REGISTRO_INICIAL,
                )
            )
            planta = self._obtener_o_fallar(uow, planta_id)

        logger.info("Planta registrada: id=%s, consecutivo=%s.", planta.id, numero)
        return planta

    def actualizar_datos(self, planta_id: int, datos: DatosPlanta) -> Planta:
        """
        Modifica los datos técnicos. Estado y consecutivo no cambian.

        Raises:
            PlantaNoEncontradaError, ValidacionError
        """
        datos = self._normalizar_y_validar(datos, self._hoy())

        with self._uow_factory() as uow:
            actual = self._obtener_o_fallar(uow, planta_id)
            self._verificar_combustible_vigente(datos, actual.datos.tipo_combustible)
            self._verificar_serie_unica(uow, datos.numero_serie, excluir_id=planta_id)
            uow.plantas.actualizar_datos(planta_id, datos)
            planta = self._obtener_o_fallar(uow, planta_id)

        logger.info("Datos técnicos actualizados: planta id=%s.", planta_id)
        return planta

    def cambiar_estado(
        self,
        planta_id: int,
        nuevo: EstadoPlanta,
        motivo: str | None = None,
        fecha: date | None = None,
        horometro: int | None = None,
    ) -> Planta:
        """
        Cambia el estado aplicando la máquina de estados y las reglas de consecutivos.

        Args:
            planta_id: Planta a modificar.
            nuevo: Estado destino.
            motivo: Obligatorio al pasar a RETIRADA, VENDIDA o DADA_DE_BAJA.
            fecha: Fecha real del cambio (por defecto, hoy). Puede ser pasada,
                   pero no futura ni anterior al último cambio registrado.
            horometro: Lectura del horómetro en el momento del cambio.
                       Obligatoria al pasar a ALQUILADA; opcional en los demás casos.
                       Nunca puede ser menor que la última lectura conocida.

        Raises:
            PlantaNoEncontradaError, TransicionInvalidaError, ValidacionError
        """
        hoy = self._hoy()
        fecha_cambio = fecha or hoy
        motivo_limpio = (motivo or "").strip() or None

        # Validaciones que no requieren consultar la base de datos.
        errores: dict[str, str] = {}
        if fecha_cambio > hoy:
            errores["fecha"] = "La fecha del cambio no puede ser futura."
        if nuevo.requiere_motivo and motivo_limpio is None:
            errores["motivo"] = f"Debe indicar el motivo para pasar a '{nuevo.etiqueta}'."
        if nuevo.requiere_horometro and horometro is None:
            errores["horometro"] = (
                f"Debe registrar la lectura del horómetro para pasar a '{nuevo.etiqueta}'."
            )
        elif horometro is not None and horometro < 0:
            errores["horometro"] = "La lectura del horómetro no puede ser negativa."
        if errores:
            raise ValidacionError(errores)

        with self._uow_factory() as uow:
            planta = self._obtener_o_fallar(uow, planta_id)
            actual = planta.estado

            if not actual.puede_pasar_a(nuevo):
                raise TransicionInvalidaError(actual, nuevo)

            # Un horómetro es como el odómetro de un carro: solo avanza.
            if horometro is not None and horometro < planta.horometro_actual:
                raise ValidacionError(
                    {
                        "horometro": (
                            f"La lectura ({horometro} h) no puede ser menor que la última "
                            f"registrada ({planta.horometro_actual} h)."
                        )
                    }
                )

            cambios = uow.historial_estados.listar_por_planta(planta_id)
            if cambios and fecha_cambio < cambios[-1].fecha:
                raise ValidacionError(
                    {
                        "fecha": (
                            "La fecha no puede ser anterior al último cambio de estado "
                            f"({cambios[-1].fecha.isoformat()})."
                        )
                    }
                )

            numero = planta.numero_consecutivo
            if actual.en_operacion and not nuevo.en_operacion:
                # Sale de operación: libera su número.
                self._consecutivos.liberar(
                    uow, planta_id, fecha_cambio, motivo_limpio or nuevo.etiqueta
                )
                numero = None
            elif not actual.en_operacion and nuevo.en_operacion:
                # Reactivación: recupera su número anterior o el menor libre.
                numero = self._consecutivos.proponer_para_reactivacion(uow, planta_id)
                self._consecutivos.registrar_asignacion(uow, planta_id, numero, fecha_cambio)

            uow.plantas.actualizar_estado(planta_id, nuevo, numero)
            uow.historial_estados.registrar(
                CambioEstado(
                    planta_id=planta_id,
                    estado_anterior=actual,
                    estado_nuevo=nuevo,
                    fecha=fecha_cambio,
                    motivo=motivo_limpio,
                    horometro=horometro,
                )
            )
            planta_actualizada = self._obtener_o_fallar(uow, planta_id)

        logger.info(
            "Planta id=%s: %s -> %s (consecutivo: %s).", planta_id, actual, nuevo, numero
        )
        return planta_actualizada

    # ------------------------------------------------------------------ #
    # Consultas (solo leen datos)
    # ------------------------------------------------------------------ #

    def obtener(self, planta_id: int) -> Planta:
        """Raises: PlantaNoEncontradaError"""
        with self._uow_factory() as uow:
            return self._obtener_o_fallar(uow, planta_id)

    def listar(
        self, incluir_fuera_de_operacion: bool = False, texto: str | None = None
    ) -> list[Planta]:
        """
        Lista plantas. Por defecto solo las que están en operación.

        Args:
            incluir_fuera_de_operacion: True para ver también retiradas,
                                        vendidas y dadas de baja.
            texto: Búsqueda por marca, modelo o número de serie.
        """
        estados = (
            None
            if incluir_fuera_de_operacion
            else {estado for estado in EstadoPlanta if estado.en_operacion}
        )
        texto_limpio = (texto or "").strip() or None
        with self._uow_factory() as uow:
            return uow.plantas.listar(estados, texto_limpio)

    def historial(
        self, planta_id: int
    ) -> tuple[list[CambioEstado], list[RegistroConsecutivo]]:
        """
        Línea de tiempo de estados y de consecutivos de una planta.

        Raises: PlantaNoEncontradaError
        """
        with self._uow_factory() as uow:
            self._obtener_o_fallar(uow, planta_id)
            return (
                uow.historial_estados.listar_por_planta(planta_id),
                uow.consecutivos.historial_de_planta(planta_id),
            )

    def quienes_tuvieron_numero(self, numero: int) -> list[RegistroConsecutivo]:
        """Responde "¿qué plantas han sido la #N?"."""
        with self._uow_factory() as uow:
            return uow.consecutivos.historial_de_numero(numero)

    def numeros_libres(self) -> list[int]:
        """Números liberados que la próxima planta podría reutilizar, en orden."""
        with self._uow_factory() as uow:
            return self._consecutivos.calcular_libres(uow.consecutivos.numeros_en_uso())

    def proximo_numero(self) -> int:
        """Número que recibirá la siguiente planta registrada (solo consulta)."""
        with self._uow_factory() as uow:
            return self._consecutivos.proponer_para_nueva(uow)

    # ------------------------------------------------------------------ #
    # Métodos internos
    # ------------------------------------------------------------------ #

    @staticmethod
    def _normalizar_y_validar(datos: DatosPlanta, hoy: date) -> DatosPlanta:
        """Limpia los datos y lanza ValidacionError si alguna regla falla."""
        datos_limpios = normalizar_datos(datos)
        errores = validar_datos(datos_limpios, hoy)
        if errores:
            raise ValidacionError(errores)
        return datos_limpios

    @staticmethod
    def _verificar_combustible_vigente(
        datos: DatosPlanta, combustible_anterior: TipoCombustible | None
    ) -> None:
        """
        Un combustible retirado (Gas) solo se admite si la planta YA lo tenía:
        se conserva el dato histórico, pero no se asigna a registros nuevos.
        """
        combustible = datos.tipo_combustible
        if (
            combustible is not None
            and not combustible.vigente
            and combustible != combustible_anterior
        ):
            raise ValidacionError(
                {
                    "tipo_combustible": (
                        f"El combustible '{combustible.etiqueta}' ya no se admite. "
                        "Elija Diésel o Gasolina."
                    )
                }
            )

    @staticmethod
    def _verificar_serie_unica(
        uow: IUnidadDeTrabajo, serie: str | None, excluir_id: int | None
    ) -> None:
        """Lanza ValidacionError si otra planta ya tiene ese número de serie."""
        if serie is not None and uow.plantas.existe_numero_serie(serie, excluir_id):
            raise ValidacionError(
                {"numero_serie": f"Ya existe otra planta con el número de serie '{serie}'."}
            )

    @staticmethod
    def _obtener_o_fallar(uow: IUnidadDeTrabajo, planta_id: int) -> Planta:
        """Devuelve la planta o lanza PlantaNoEncontradaError."""
        planta = uow.plantas.obtener(planta_id)
        if planta is None:
            raise PlantaNoEncontradaError(planta_id)
        return planta
