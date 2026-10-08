"""
Casos de uso del módulo de gastos (Actividad 4.1).

Ruta: src/business/services/gasto_service.py

Reglas aprobadas:
1. Cada gasto pertenece a una planta.
2. La factura es opcional (sin ella, el gasto queda "sin soporte").
3. Una factura puede repartirse entre plantas, sin superar su valor total.
4. Un proveedor no puede repetir un número de factura.
5. No se registran gastos a plantas vendidas o dadas de baja.
6. La fecha no puede ser futura.
7. Los gastos no se editan ni se borran: se anulan con motivo.
"""

import logging
from collections.abc import Callable
from datetime import date

from src.business.exceptions import (
    NegocioError,
    PlantaNoEncontradaError,
    RegistroNoEncontradoError,
    ValidacionError,
)
from src.business.interfaces.unidad_de_trabajo import FabricaUnidadDeTrabajo, IUnidadDeTrabajo
from src.business.models.gasto import (
    CategoriaGasto,
    DatosFactura,
    DatosGasto,
    FacturaProveedor,
    Gasto,
    GastoDetalle,
    Proveedor,
    ResumenGastos,
)
from src.business.validators.gasto_validator import (
    normalizar_factura,
    normalizar_gasto,
    validar_factura,
    validar_gasto,
)
from src.shared.formatters import formatear_moneda

logger = logging.getLogger(__name__)


class GastoService:
    """Registro, anulación y consulta de gastos, facturas y proveedores."""

    def __init__(
        self, uow_factory: FabricaUnidadDeTrabajo, hoy: Callable[[], date] = date.today
    ) -> None:
        self._uow_factory = uow_factory
        self._hoy = hoy

    # ------------------------------------------------------------------ #
    # Gastos
    # ------------------------------------------------------------------ #

    def registrar_gasto(self, planta_id: int, datos: DatosGasto) -> Gasto:
        """
        Raises:
            PlantaNoEncontradaError, ValidacionError
        """
        datos = normalizar_gasto(datos)
        errores = validar_gasto(datos, self._hoy())
        if errores:
            raise ValidacionError(errores)

        with self._uow_factory() as uow:
            planta = uow.plantas.obtener(planta_id)
            if planta is None:
                raise PlantaNoEncontradaError(planta_id)
            if planta.estado.es_final:
                raise ValidacionError(
                    {
                        "planta": (
                            "No se pueden registrar gastos de una planta en estado "
                            f"'{planta.estado.etiqueta}'."
                        )
                    }
                )
            categoria = uow.categorias.obtener(datos.categoria_id)
            if categoria is None or not categoria.activo:
                raise ValidacionError({"categoria_id": "Seleccione una categoría válida."})

            if datos.factura_id is not None:
                factura = uow.facturas.obtener(datos.factura_id)
                if factura is None:
                    raise ValidacionError({"factura_id": "La factura seleccionada no existe."})
                # Dentro de la misma transacción: dos registros simultáneos no
                # pueden gastar el mismo saldo dos veces.
                if datos.valor_total > factura.saldo_por_asignar:
                    raise ValidacionError(
                        {
                            "valor_total": (
                                f"Supera el saldo por asignar de la factura "
                                f"{factura.datos.numero_factura} "
                                f"({formatear_moneda(factura.saldo_por_asignar)})."
                            )
                        }
                    )

            gasto_id = uow.gastos.insertar(planta_id, datos)
            gasto = self._obtener_gasto(uow, gasto_id)

        logger.info(
            "Gasto id=%s registrado a la planta id=%s por %s.",
            gasto_id,
            planta_id,
            datos.valor_total,
        )
        return gasto

    def anular_gasto(self, gasto_id: int, motivo: str) -> Gasto:
        """
        Marca el gasto como anulado. No se borra: queda visible como corrección.

        Raises:
            RegistroNoEncontradoError, ValidacionError, NegocioError
        """
        motivo_limpio = (motivo or "").strip()
        if not motivo_limpio:
            raise ValidacionError({"motivo": "Debe indicar el motivo de la anulación."})

        with self._uow_factory() as uow:
            gasto = self._obtener_gasto(uow, gasto_id)
            if gasto.anulado:
                raise NegocioError("Este gasto ya estaba anulado.")
            uow.gastos.anular(gasto_id, motivo_limpio)
            anulado = self._obtener_gasto(uow, gasto_id)

        logger.info("Gasto id=%s anulado. Motivo: %s", gasto_id, motivo_limpio)
        return anulado

    def listar_gastos(self, planta_id: int, incluir_anulados: bool = False) -> list[GastoDetalle]:
        with self._uow_factory() as uow:
            return uow.gastos.listar_por_planta(planta_id, incluir_anulados)

    def resumen(self, planta_id: int) -> ResumenGastos:
        with self._uow_factory() as uow:
            return uow.gastos.resumen_por_planta(planta_id)

    # ------------------------------------------------------------------ #
    # Facturas
    # ------------------------------------------------------------------ #

    def registrar_factura(self, datos: DatosFactura) -> FacturaProveedor:
        """
        Raises:
            ValidacionError
        """
        datos = normalizar_factura(datos)
        errores = validar_factura(datos, self._hoy())
        if errores:
            raise ValidacionError(errores)

        with self._uow_factory() as uow:
            proveedor = uow.proveedores.obtener(datos.proveedor_id)
            if proveedor is None or not proveedor.activo:
                raise ValidacionError({"proveedor_id": "Seleccione un proveedor válido."})
            if uow.facturas.existe_numero(datos.proveedor_id, datos.numero_factura):
                raise ValidacionError(
                    {
                        "numero_factura": (
                            f"El proveedor {proveedor.nombre} ya tiene registrada la "
                            f"factura {datos.numero_factura}."
                        )
                    }
                )
            factura_id = uow.facturas.insertar(datos)
            factura = uow.facturas.obtener(factura_id)
            if factura is None:  # No debería ocurrir: se acaba de insertar
                raise RegistroNoEncontradoError(f"No se encontró la factura id={factura_id}.")

        logger.info("Factura %s registrada (id=%s).", datos.numero_factura, factura_id)
        return factura

    def facturas_con_saldo(self, texto: str | None = None) -> list[FacturaProveedor]:
        """Facturas a las que todavía se les puede asignar gastos."""
        with self._uow_factory() as uow:
            return uow.facturas.listar_con_saldo((texto or "").strip() or None)

    # ------------------------------------------------------------------ #
    # Proveedores y categorías
    # ------------------------------------------------------------------ #

    def registrar_proveedor(
        self, nombre: str, nit: str | None = None, telefono: str | None = None
    ) -> Proveedor:
        """
        El nombre y el NIT no se pueden repetir (sin distinguir mayúsculas), para
        evitar "Filtros SAS" y "filtros sas" como dos proveedores distintos.

        Raises:
            ValidacionError
        """
        nombre_limpio = (nombre or "").strip()
        nit_limpio = (nit or "").strip() or None
        telefono_limpio = (telefono or "").strip() or None
        if not nombre_limpio:
            raise ValidacionError({"nombre": "El nombre del proveedor es obligatorio."})

        with self._uow_factory() as uow:
            errores: dict[str, str] = {}
            if uow.proveedores.existe_nombre(nombre_limpio):
                errores["nombre"] = f"Ya existe un proveedor llamado '{nombre_limpio}'."
            if nit_limpio and uow.proveedores.existe_nit(nit_limpio):
                errores["nit"] = f"Ya existe un proveedor con el NIT {nit_limpio}."
            if errores:
                raise ValidacionError(errores)
            proveedor_id = uow.proveedores.insertar(nombre_limpio, nit_limpio, telefono_limpio)
            proveedor = uow.proveedores.obtener(proveedor_id)
            if proveedor is None:  # No debería ocurrir: se acaba de insertar
                raise RegistroNoEncontradoError(f"No se encontró el proveedor id={proveedor_id}.")

        logger.info("Proveedor registrado: %s (id=%s).", nombre_limpio, proveedor_id)
        return proveedor

    def listar_proveedores(self) -> list[Proveedor]:
        with self._uow_factory() as uow:
            return uow.proveedores.listar()

    def listar_categorias(self) -> list[CategoriaGasto]:
        with self._uow_factory() as uow:
            return uow.categorias.listar()

    # ------------------------------------------------------------------ #
    # Internos
    # ------------------------------------------------------------------ #

    @staticmethod
    def _obtener_gasto(uow: IUnidadDeTrabajo, gasto_id: int) -> Gasto:
        gasto = uow.gastos.obtener(gasto_id)
        if gasto is None:
            raise RegistroNoEncontradoError(f"No existe un gasto con id {gasto_id}.")
        return gasto
