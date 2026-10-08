"""
Casos de uso comerciales: alquilar, devolver, vender y cobrar (Actividad 4.3).

Ruta: src/business/services/comercial_service.py

Cada operación cambia el estado de la planta JUNTO con sus datos comerciales,
en una sola transacción: o queda el contrato y el cambio de estado, o nada.

Reglas aprobadas:
1. Un contrato por planta y cliente; nunca dos contratos activos a la vez.
2. Tarifa obligatoria y mayor que cero; modalidad por día o por mes.
3-4. Liquidación por el tiempo real de uso (ver liquidacion.py).
5. Cobros parciales durante el alquiler; al cerrar se descuenta lo ya cobrado.
6. Los ingresos se anulan con motivo; no se editan ni se borran.
7. Las condiciones se corrigen solo mientras el contrato está activo.
8. Clientes con nombre y documento únicos.
"""

import logging
from collections.abc import Callable
from datetime import date

from src.business.exceptions import (
    NegocioError,
    PlantaNoEncontradaError,
    RegistroNoEncontradoError,
    TransicionInvalidaError,
    ValidacionError,
)
from src.business.interfaces.unidad_de_trabajo import FabricaUnidadDeTrabajo, IUnidadDeTrabajo
from src.business.models.comercial import (
    Alquiler,
    Cliente,
    DatosContrato,
    DatosIngreso,
    DatosVenta,
    Ingreso,
    Liquidacion,
    TipoIngreso,
)
from src.business.models.estado_planta import EstadoPlanta
from src.business.services.liquidacion import calcular_liquidacion
from src.business.services.planta_service import PlantaService
from src.shared.formatters import formatear_moneda

logger = logging.getLogger(__name__)

_FORMATO = "%d/%m/%Y"


class ComercialService:
    """Contratos de alquiler, ventas, cobros y clientes."""

    def __init__(
        self,
        uow_factory: FabricaUnidadDeTrabajo,
        plantas: PlantaService,
        hoy: Callable[[], date] = date.today,
    ) -> None:
        """
        Args:
            plantas: Se reutiliza su máquina de estados (cambiar_estado_en) para que
                las reglas de transición, horómetro y consecutivos sean las mismas.
        """
        self._uow_factory = uow_factory
        self._plantas = plantas
        self._hoy = hoy

    # ------------------------------------------------------------------ #
    # Alquiler y devolución
    # ------------------------------------------------------------------ #

    def alquilar(
        self,
        planta_id: int,
        contrato: DatosContrato,
        horometro: int,
        fecha: date | None = None,
        motivo: str | None = None,
    ) -> Alquiler:
        """
        Contrato + cambio a ALQUILADA + lectura de salida ligada al contrato.

        Raises:
            PlantaNoEncontradaError, TransicionInvalidaError, ValidacionError
        """
        contrato = self._validar_contrato(contrato)
        fecha_inicio = fecha or self._hoy()
        with self._uow_factory() as uow:
            planta = uow.plantas.obtener(planta_id)
            if planta is None:
                raise PlantaNoEncontradaError(planta_id)
            self._verificar_cliente(uow, contrato.cliente_id)
            # Primero la transición: si no es válida, no se crea ningún contrato.
            if not planta.estado.puede_pasar_a(EstadoPlanta.ALQUILADA):
                raise TransicionInvalidaError(planta.estado, EstadoPlanta.ALQUILADA)
            alquiler_id = uow.alquileres.insertar(planta_id, contrato, fecha_inicio)
            self._plantas.cambiar_estado_en(
                uow,
                planta_id,
                EstadoPlanta.ALQUILADA,
                motivo,
                fecha_inicio,
                horometro,
                alquiler_id=alquiler_id,
            )
            alquiler = self._obtener(uow, alquiler_id)
        logger.info("Planta id=%s alquilada (contrato id=%s).", planta_id, alquiler_id)
        return alquiler

    def liquidacion_preliminar(
        self, planta_id: int, fecha: date | None = None
    ) -> tuple[Alquiler, Liquidacion] | None:
        """
        Lo que se cobraría si la planta se devolviera en esa fecha (solo consulta).
        None si la planta no tiene contrato activo (por ejemplo, alquileres antiguos).
        """
        with self._uow_factory() as uow:
            activo = uow.alquileres.activo_de(planta_id)
        if activo is None:
            return None
        fin = max(fecha or self._hoy(), activo.fecha_inicio)
        return activo, calcular_liquidacion(
            activo.modalidad, activo.tarifa, activo.fecha_inicio, fin
        )

    def devolver(
        self,
        planta_id: int,
        nuevo_estado: EstadoPlanta = EstadoPlanta.DISPONIBLE,
        fecha: date | None = None,
        horometro: int | None = None,
        motivo: str | None = None,
        valor_liquidado: int | None = None,
        cobrar_saldo: bool = False,
        numero_documento: str | None = None,
    ) -> Alquiler | None:
        """
        Cierra el contrato con su liquidación y saca la planta de ALQUILADA.

        Args:
            valor_liquidado: Valor acordado; por defecto, el calculado. Puede ser
                menor (descuento negociado), pero nunca menor que lo ya cobrado.
            cobrar_saldo: Registrar ya el ingreso por el saldo pendiente.

        Returns:
            El contrato cerrado, o None si era un alquiler sin contrato (anterior
            a la versión 0.7.0): en ese caso solo cambia el estado.
        """
        fecha_fin = fecha or self._hoy()
        with self._uow_factory() as uow:
            activo = uow.alquileres.activo_de(planta_id)
            if activo is None:
                self._plantas.cambiar_estado_en(
                    uow, planta_id, nuevo_estado, motivo, fecha_fin, horometro
                )
                return None

            if fecha_fin < activo.fecha_inicio:
                raise ValidacionError(
                    {
                        "fecha": f"La devolución no puede ser anterior a la entrega "
                        f"({activo.fecha_inicio:{_FORMATO}})."
                    }
                )
            calculado = calcular_liquidacion(
                activo.modalidad, activo.tarifa, activo.fecha_inicio, fecha_fin
            ).valor
            valor = calculado if valor_liquidado is None else valor_liquidado
            if valor < activo.cobrado:
                raise ValidacionError(
                    {
                        "valor_liquidado": (
                            f"El valor liquidado no puede ser menor que lo ya cobrado "
                            f"({formatear_moneda(activo.cobrado)})."
                        )
                    }
                )

            uow.alquileres.cerrar(activo.id, fecha_fin, valor)
            self._plantas.cambiar_estado_en(
                uow, planta_id, nuevo_estado, motivo, fecha_fin, horometro, alquiler_id=activo.id
            )
            saldo = valor - activo.cobrado
            if cobrar_saldo and saldo > 0:
                uow.ingresos.insertar(
                    planta_id,
                    TipoIngreso.ALQUILER,
                    DatosIngreso(
                        fecha_fin,
                        f"Liquidación del alquiler {activo.fecha_inicio:{_FORMATO}} – "
                        f"{fecha_fin:{_FORMATO}}",
                        saldo,
                        (numero_documento or "").strip() or None,
                    ),
                    alquiler_id=activo.id,
                    cliente_id=activo.cliente_id,
                )
            cerrado = self._obtener(uow, activo.id)
        logger.info("Contrato id=%s cerrado por %s.", activo.id, valor)
        return cerrado

    def corregir_contrato(self, alquiler_id: int, contrato: DatosContrato) -> Alquiler:
        """Regla 7: las condiciones solo se corrigen mientras el contrato está activo."""
        contrato = self._validar_contrato(contrato)
        with self._uow_factory() as uow:
            alquiler = self._obtener(uow, alquiler_id)
            if not alquiler.activo:
                raise NegocioError("Un contrato cerrado no se puede modificar.")
            self._verificar_cliente(uow, contrato.cliente_id)
            uow.alquileres.actualizar_condiciones(alquiler_id, contrato)
            return self._obtener(uow, alquiler_id)

    # ------------------------------------------------------------------ #
    # Cobros, ventas e ingresos
    # ------------------------------------------------------------------ #

    def registrar_cobro(self, alquiler_id: int, datos: DatosIngreso) -> Ingreso:
        """
        Cobro ligado a un contrato. Durante el alquiler se admiten anticipos sin
        tope; en un contrato cerrado, el cobro no puede superar el saldo pendiente.
        """
        datos = self._validar_ingreso(datos)
        with self._uow_factory() as uow:
            alquiler = self._obtener(uow, alquiler_id)
            if datos.fecha < alquiler.fecha_inicio:
                raise ValidacionError({"fecha": "El cobro no puede ser anterior a la entrega."})
            if alquiler.saldo is not None and datos.valor > alquiler.saldo:
                raise ValidacionError(
                    {"valor": f"Supera el saldo pendiente ({formatear_moneda(alquiler.saldo)})."}
                )
            ingreso_id = uow.ingresos.insertar(
                alquiler.planta_id,
                TipoIngreso.ALQUILER,
                datos,
                alquiler_id=alquiler_id,
                cliente_id=alquiler.cliente_id,
            )
            return self._obtener_ingreso(uow, ingreso_id)

    def vender(
        self,
        planta_id: int,
        venta: DatosVenta,
        fecha: date | None = None,
        motivo: str | None = None,
    ) -> Ingreso:
        """Cambio a VENDIDA + ingreso de la venta, en una sola transacción."""
        errores: dict[str, str] = {}
        if venta.valor <= 0:
            errores["valor"] = "El precio de venta debe ser mayor que 0."
        if errores:
            raise ValidacionError(errores)
        fecha_venta = fecha or self._hoy()
        with self._uow_factory() as uow:
            cliente = self._verificar_cliente(uow, venta.cliente_id)
            self._plantas.cambiar_estado_en(
                uow,
                planta_id,
                EstadoPlanta.VENDIDA,
                (motivo or "").strip() or f"Venta a {cliente.nombre}",
                fecha_venta,
            )
            ingreso_id = uow.ingresos.insertar(
                planta_id,
                TipoIngreso.VENTA,
                DatosIngreso(
                    fecha_venta,
                    f"Venta de la planta a {cliente.nombre}",
                    venta.valor,
                    (venta.numero_documento or "").strip() or None,
                ),
                cliente_id=cliente.id,
            )
            ingreso = self._obtener_ingreso(uow, ingreso_id)
        logger.info("Planta id=%s vendida por %s.", planta_id, venta.valor)
        return ingreso

    def registrar_ingreso(
        self, planta_id: int, datos: DatosIngreso, cliente_id: int | None = None
    ) -> Ingreso:
        """Ingreso de tipo "Otro" (por ejemplo, el cobro de un alquiler antiguo sin contrato)."""
        datos = self._validar_ingreso(datos)
        with self._uow_factory() as uow:
            if uow.plantas.obtener(planta_id) is None:
                raise PlantaNoEncontradaError(planta_id)
            if cliente_id is not None:
                self._verificar_cliente(uow, cliente_id)
            ingreso_id = uow.ingresos.insertar(
                planta_id, TipoIngreso.OTRO, datos, cliente_id=cliente_id
            )
            return self._obtener_ingreso(uow, ingreso_id)

    def anular_ingreso(self, ingreso_id: int, motivo: str) -> Ingreso:
        motivo_limpio = (motivo or "").strip()
        if not motivo_limpio:
            raise ValidacionError({"motivo": "Debe indicar el motivo de la anulación."})
        with self._uow_factory() as uow:
            ingreso = self._obtener_ingreso(uow, ingreso_id)
            if ingreso.anulado:
                raise NegocioError("Este ingreso ya estaba anulado.")
            uow.ingresos.anular(ingreso_id, motivo_limpio)
            return self._obtener_ingreso(uow, ingreso_id)

    # ------------------------------------------------------------------ #
    # Consultas
    # ------------------------------------------------------------------ #

    def contrato_activo(self, planta_id: int) -> Alquiler | None:
        with self._uow_factory() as uow:
            return uow.alquileres.activo_de(planta_id)

    def alquileres(self, planta_id: int) -> list[Alquiler]:
        with self._uow_factory() as uow:
            return uow.alquileres.listar_por_planta(planta_id)

    def ingresos(self, planta_id: int, incluir_anulados: bool = False) -> list[Ingreso]:
        with self._uow_factory() as uow:
            return uow.ingresos.listar_por_planta(planta_id, incluir_anulados)

    def clientes_actuales(self) -> dict[int, str]:
        """{planta_id: cliente} de las plantas alquiladas con contrato."""
        with self._uow_factory() as uow:
            return uow.alquileres.clientes_actuales()

    # ------------------------------------------------------------------ #
    # Clientes
    # ------------------------------------------------------------------ #

    def registrar_cliente(
        self, nombre: str, documento: str | None = None, telefono: str | None = None
    ) -> Cliente:
        nombre_limpio = (nombre or "").strip()
        documento_limpio = (documento or "").strip() or None
        if not nombre_limpio:
            raise ValidacionError({"nombre": "El nombre del cliente es obligatorio."})
        with self._uow_factory() as uow:
            errores: dict[str, str] = {}
            if uow.clientes.existe_nombre(nombre_limpio):
                errores["nombre"] = f"Ya existe un cliente llamado '{nombre_limpio}'."
            if documento_limpio and uow.clientes.existe_documento(documento_limpio):
                errores["documento"] = f"Ya existe un cliente con el documento {documento_limpio}."
            if errores:
                raise ValidacionError(errores)
            cliente_id = uow.clientes.insertar(
                nombre_limpio, documento_limpio, (telefono or "").strip() or None
            )
            return self._verificar_cliente(uow, cliente_id)

    def listar_clientes(self) -> list[Cliente]:
        with self._uow_factory() as uow:
            return uow.clientes.listar()

    # ------------------------------------------------------------------ #
    # Internos
    # ------------------------------------------------------------------ #

    @staticmethod
    def _validar_contrato(contrato: DatosContrato) -> DatosContrato:
        if contrato.tarifa <= 0:
            raise ValidacionError({"tarifa": "La tarifa debe ser mayor que 0."})
        observaciones = (contrato.observaciones or "").strip() or None
        return DatosContrato(
            contrato.cliente_id, contrato.modalidad, contrato.tarifa, observaciones
        )

    def _validar_ingreso(self, datos: DatosIngreso) -> DatosIngreso:
        datos = DatosIngreso(
            datos.fecha,
            (datos.descripcion or "").strip(),
            datos.valor,
            (datos.numero_documento or "").strip() or None,
        )
        errores: dict[str, str] = {}
        if not datos.descripcion:
            errores["descripcion"] = "La descripción es obligatoria."
        if datos.valor <= 0:
            errores["valor"] = "El valor debe ser mayor que 0."
        if datos.fecha > self._hoy():
            errores["fecha"] = "La fecha no puede ser futura."
        if errores:
            raise ValidacionError(errores)
        return datos

    @staticmethod
    def _verificar_cliente(uow: IUnidadDeTrabajo, cliente_id: int) -> Cliente:
        cliente = uow.clientes.obtener(cliente_id)
        if cliente is None or not cliente.activo:
            raise ValidacionError({"cliente_id": "Seleccione un cliente válido."})
        return cliente

    @staticmethod
    def _obtener(uow: IUnidadDeTrabajo, alquiler_id: int) -> Alquiler:
        alquiler = uow.alquileres.obtener(alquiler_id)
        if alquiler is None:
            raise RegistroNoEncontradoError(f"No existe un contrato con id {alquiler_id}.")
        return alquiler

    @staticmethod
    def _obtener_ingreso(uow: IUnidadDeTrabajo, ingreso_id: int) -> Ingreso:
        ingreso = uow.ingresos.obtener(ingreso_id)
        if ingreso is None:
            raise RegistroNoEncontradoError(f"No existe un ingreso con id {ingreso_id}.")
        return ingreso
