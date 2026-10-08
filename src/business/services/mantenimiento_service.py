"""
Casos de uso del módulo de mantenimientos (Actividad 4.2).

Ruta: src/business/services/mantenimiento_service.py

Reglas aprobadas:
1. Cada mantenimiento pertenece a una planta; no a vendidas ni dadas de baja.
2. Tipo preventivo o correctivo.
3. El horómetro es obligatorio y nunca retrocede.
4. La fecha no es futura ni anterior al último mantenimiento.
5. El próximo se programa por fecha, por horas o por ambas, siempre después.
6. Insumos y mano de obra se guardan como gastos ligados, en una sola transacción.
7. No se borran: se anulan con motivo, junto con sus gastos.
"""

import logging
from collections.abc import Callable
from datetime import date

from src.business.calendario import sumar_meses
from src.business.exceptions import (
    NegocioError,
    PlantaNoEncontradaError,
    RegistroNoEncontradoError,
    ValidacionError,
)
from src.business.interfaces.unidad_de_trabajo import FabricaUnidadDeTrabajo, IUnidadDeTrabajo
from src.business.models.estado_planta import EstadoPlanta
from src.business.models.gasto import DatosGasto
from src.business.models.mantenimiento import (
    AlertaMantenimiento,
    DatosMantenimiento,
    LineaInsumo,
    Mantenimiento,
    NivelAlerta,
)
from src.business.validators.mantenimiento_validator import (
    normalizar_insumo,
    normalizar_mantenimiento,
    validar_insumos,
    validar_mantenimiento,
)
from src.shared.formatters import formatear_entero, formatear_moneda

logger = logging.getLogger(__name__)


class MantenimientoService:
    """Registro, anulación, consulta y alertas de mantenimientos."""

    def __init__(
        self,
        uow_factory: FabricaUnidadDeTrabajo,
        hoy: Callable[[], date] = date.today,
        dias_alerta: int = 15,
        horas_alerta: int = 25,
    ) -> None:
        """
        Args:
            dias_alerta / horas_alerta: anticipación con la que un mantenimiento
                programado pasa a "Próximo" (en la app vienen de settings.py).
        """
        self._uow_factory = uow_factory
        self._hoy = hoy
        self._dias_alerta = dias_alerta
        self._horas_alerta = horas_alerta

    # ------------------------------------------------------------------ #
    # Registro y anulación
    # ------------------------------------------------------------------ #

    def registrar(
        self,
        planta_id: int,
        datos: DatosMantenimiento,
        insumos: list[LineaInsumo] | None = None,
        factura_id: int | None = None,
    ) -> Mantenimiento:
        """
        Guarda el mantenimiento y sus insumos como gastos ligados: todo o nada.

        Args:
            factura_id: Factura que respalda TODOS los insumos (o None: sin soporte).

        Raises:
            PlantaNoEncontradaError, ValidacionError
        """
        datos = normalizar_mantenimiento(datos)
        lineas = [normalizar_insumo(linea) for linea in insumos or []]
        errores = validar_mantenimiento(datos, self._hoy())
        problema_insumos = validar_insumos(lineas)
        if problema_insumos:
            errores["insumos"] = problema_insumos
        if factura_id is not None and not lineas:
            errores["factura_id"] = "Agregue al menos un insumo para asociar la factura."
        if errores:
            raise ValidacionError(errores)

        with self._uow_factory() as uow:
            planta = uow.plantas.obtener(planta_id)
            if planta is None:
                raise PlantaNoEncontradaError(planta_id)
            self._verificar_contexto(uow, planta_id, planta.estado, planta.horometro_actual, datos)
            self._verificar_insumos_y_factura(uow, lineas, factura_id)

            mantenimiento_id = uow.mantenimientos.insertar(planta_id, datos)
            for linea in lineas:
                uow.gastos.insertar(
                    planta_id,
                    DatosGasto(
                        categoria_id=linea.categoria_id,
                        fecha=datos.fecha,
                        descripcion=linea.descripcion,
                        valor_total=linea.valor_total,
                        cantidad=linea.cantidad,
                        unidad=linea.unidad,
                        factura_id=factura_id,
                    ),
                    mantenimiento_id=mantenimiento_id,
                )
            mantenimiento = self._obtener(uow, mantenimiento_id)

        logger.info(
            "Mantenimiento id=%s registrado a la planta id=%s con %s insumo(s).",
            mantenimiento_id,
            planta_id,
            len(lineas),
        )
        return mantenimiento

    def anular(self, mantenimiento_id: int, motivo: str) -> Mantenimiento:
        """
        Anula el mantenimiento y sus gastos; su lectura del horómetro deja de contar.

        Raises:
            RegistroNoEncontradoError, ValidacionError, NegocioError
        """
        motivo_limpio = (motivo or "").strip()
        if not motivo_limpio:
            raise ValidacionError({"motivo": "Debe indicar el motivo de la anulación."})

        with self._uow_factory() as uow:
            mantenimiento = self._obtener(uow, mantenimiento_id)
            if mantenimiento.anulado:
                raise NegocioError("Este mantenimiento ya estaba anulado.")
            uow.mantenimientos.anular(mantenimiento_id, motivo_limpio)
            uow.gastos.anular_por_mantenimiento(
                mantenimiento_id, f"Mantenimiento anulado: {motivo_limpio}"
            )
            anulado = self._obtener(uow, mantenimiento_id)

        logger.info("Mantenimiento id=%s anulado. Motivo: %s", mantenimiento_id, motivo_limpio)
        return anulado

    # ------------------------------------------------------------------ #
    # Consultas
    # ------------------------------------------------------------------ #

    def listar(self, planta_id: int, incluir_anulados: bool = False) -> list[Mantenimiento]:
        with self._uow_factory() as uow:
            return uow.mantenimientos.listar_por_planta(planta_id, incluir_anulados)

    def ultimo(self, planta_id: int) -> Mantenimiento | None:
        with self._uow_factory() as uow:
            return uow.mantenimientos.ultimo_vigente(planta_id)

    def tecnicos(self) -> list[str]:
        with self._uow_factory() as uow:
            return uow.mantenimientos.tecnicos_registrados()

    def alertas(self) -> list[AlertaMantenimiento]:
        """
        Plantas en operación cuyo ÚLTIMO mantenimiento programó uno siguiente
        que ya venció o está cerca. Primero las vencidas; luego, por número.
        """
        hoy = self._hoy()
        en_operacion = {e for e in EstadoPlanta if e.en_operacion}
        with self._uow_factory() as uow:
            plantas = uow.plantas.listar(en_operacion)
            ultimos = uow.mantenimientos.ultimos_por_planta()

        alertas: list[AlertaMantenimiento] = []
        for planta in plantas:
            ultimo = ultimos.get(planta.id)
            if ultimo is None or not ultimo.tiene_programacion:
                continue
            proxima_fecha = ultimo.datos.proxima_fecha
            proximo_horometro = ultimo.datos.proximo_horometro
            dias = (proxima_fecha - hoy).days if proxima_fecha else None
            horas = proximo_horometro - planta.horometro_actual if proximo_horometro else None

            if (dias is not None and dias <= 0) or (horas is not None and horas <= 0):
                nivel = NivelAlerta.VENCIDO
            elif (dias is not None and dias <= self._dias_alerta) or (
                horas is not None and horas <= self._horas_alerta
            ):
                nivel = NivelAlerta.PROXIMO
            else:
                continue
            alertas.append(
                AlertaMantenimiento(planta, nivel, proxima_fecha, proximo_horometro, dias, horas)
            )

        # Primero las vencidas y, dentro de cada grupo, por número consecutivo.
        # (No se ordena por "urgencia": eso mezclaría días con horas, que no son
        # comparables. Un orden fijo permite encontrar cada planta siempre igual.)
        alertas.sort(
            key=lambda a: (
                a.nivel is not NivelAlerta.VENCIDO,
                a.planta.numero_consecutivo or 0,
            )
        )
        return alertas

    @staticmethod
    def proximo_sugerido(
        fecha: date, horometro: int, intervalo_meses: int, intervalo_horas: int
    ) -> tuple[date, int]:
        """
        Fecha y horas sugeridas para el siguiente preventivo.

        Suma meses de calendario respetando el fin de mes: 31 de agosto + 6 meses
        = 28 (o 29) de febrero, no un "31 de febrero" inexistente.
        """
        return sumar_meses(fecha, intervalo_meses), horometro + intervalo_horas

    # ------------------------------------------------------------------ #
    # Internos
    # ------------------------------------------------------------------ #

    @staticmethod
    def _verificar_contexto(
        uow: IUnidadDeTrabajo,
        planta_id: int,
        estado: EstadoPlanta,
        horometro_actual: int,
        datos: DatosMantenimiento,
    ) -> None:
        """Reglas 1, 3 y 4: estado de la planta, horómetro y orden de las fechas."""
        if estado.es_final:
            raise ValidacionError(
                {
                    "planta": (
                        "No se registran mantenimientos de una planta en estado "
                        f"'{estado.etiqueta}'."
                    )
                }
            )
        errores: dict[str, str] = {}
        if datos.horometro < horometro_actual:
            errores["horometro"] = (
                f"La lectura ({formatear_entero(datos.horometro, 'h')}) no puede ser menor "
                f"que la última registrada ({formatear_entero(horometro_actual, 'h')})."
            )
        ultimo = uow.mantenimientos.ultimo_vigente(planta_id)
        if ultimo is not None and datos.fecha < ultimo.datos.fecha:
            errores["fecha"] = (
                "La fecha no puede ser anterior al último mantenimiento "
                f"({ultimo.datos.fecha:%d/%m/%Y})."
            )
        if errores:
            raise ValidacionError(errores)

    @staticmethod
    def _verificar_insumos_y_factura(
        uow: IUnidadDeTrabajo, lineas: list[LineaInsumo], factura_id: int | None
    ) -> None:
        """Regla 6: categorías válidas y, con factura, total dentro de su saldo."""
        for numero, linea in enumerate(lineas, start=1):
            categoria = uow.categorias.obtener(linea.categoria_id)
            if categoria is None or not categoria.activo:
                raise ValidacionError({"insumos": f"Línea {numero}: categoría no válida."})
        if factura_id is None:
            return
        factura = uow.facturas.obtener(factura_id)
        if factura is None:
            raise ValidacionError({"factura_id": "La factura seleccionada no existe."})
        total = sum(linea.valor_total for linea in lineas)
        if total > factura.saldo_por_asignar:
            raise ValidacionError(
                {
                    "insumos": (
                        f"El total de los insumos ({formatear_moneda(total)}) supera el saldo "
                        f"de la factura {factura.datos.numero_factura} "
                        f"({formatear_moneda(factura.saldo_por_asignar)})."
                    )
                }
            )

    @staticmethod
    def _obtener(uow: IUnidadDeTrabajo, mantenimiento_id: int) -> Mantenimiento:
        mantenimiento = uow.mantenimientos.obtener(mantenimiento_id)
        if mantenimiento is None:
            raise RegistroNoEncontradoError(
                f"No existe un mantenimiento con id {mantenimiento_id}."
            )
        return mantenimiento
