"""
Controlador de la ficha de una planta (historial y gastos).

Ruta: src/presentation/controllers/ficha_controller.py

Coordina la ventana de la ficha con PlantaService y GastoService. Cada
sub-iteración de la Actividad 4 agregará aquí la lógica de su pestaña.
"""

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, Final, Protocol

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog, QMessageBox, QWidget

from src.business.exceptions import NegocioError, ValidacionError
from src.business.models.gasto import DatosFactura, DatosGasto, FacturaProveedor, GastoDetalle
from src.business.models.mantenimiento import (
    DatosMantenimiento,
    LineaInsumo,
    Mantenimiento,
    TipoMantenimiento,
)
from src.business.models.planta import Planta
from src.business.services.gasto_service import GastoService
from src.business.services.mantenimiento_service import MantenimientoService
from src.business.services.planta_service import PlantaService
from src.presentation.controllers.textos import (
    FORMATO_FECHA,
    describir_planta,
    filas_historial_consecutivos,
    filas_historial_estados,
)
from src.presentation.dialogs.ficha_planta_dialog import FichaPlantaDialog
from src.presentation.dialogs.gasto_dialogs import (
    NuevaFacturaDialog,
    NuevoProveedorDialog,
    OpcionFactura,
    RegistrarGastoDialog,
)
from src.presentation.dialogs.mantenimiento_dialog import (
    InsumoSugerido,
    RegistrarMantenimientoDialog,
)
from src.presentation.widgets.formulario_base import FormularioBase
from src.presentation.widgets.gastos_widget import FilaGasto
from src.presentation.widgets.registros_widget import FilaRegistro
from src.shared.formatters import formatear_decimal, formatear_entero, formatear_moneda

logger = logging.getLogger(__name__)

UNIDADES: Final[list[str]] = ["Unidad", "Galón", "Litro", "Cuarto", "Servicio"]
TIPOS_MANTENIMIENTO: Final[list[tuple[str, str]]] = [
    (t.etiqueta, t.value) for t in TipoMantenimiento
]
_ERROR_INESPERADO: Final[str] = (
    "Ocurrió un error inesperado. Los detalles quedaron registrados en el log."
)


class _ConFacturas(Protocol):
    """Formulario que ofrece facturas (el de gasto o el de mantenimiento)."""

    def set_facturas(
        self, facturas: list[OpcionFactura], seleccionar: int | None = None
    ) -> None: ...


class FichaPlantaController(QObject):
    """Abre la ficha de una planta y atiende sus pestañas."""

    def __init__(
        self,
        plantas: PlantaService,
        gastos: GastoService,
        mantenimientos: MantenimientoService,
        ventana_padre: QWidget,
        parent: QObject | None = None,
        intervalo_meses: int = 6,
        intervalo_horas: int = 250,
    ) -> None:
        """
        Args:
            intervalo_meses / intervalo_horas: sugerencia del próximo preventivo
                (en la aplicación vienen de settings.py).
        """
        super().__init__(parent)
        self._plantas = plantas
        self._gastos = gastos
        self._mantenimientos = mantenimientos
        self._intervalo_meses = intervalo_meses
        self._intervalo_horas = intervalo_horas
        self._ventana_padre = ventana_padre
        self._planta: Planta | None = None
        self._ficha: FichaPlantaDialog | None = None
        self._ver_anulados = False
        self._ver_mantenimientos_anulados = False

    # ------------------------------------------------------------------ #
    # Apertura
    # ------------------------------------------------------------------ #

    def abrir(self, planta_id: int, pestana: str = "Historial") -> None:
        try:
            planta = self._plantas.obtener(planta_id)
            cambios, consecutivos = self._plantas.historial(planta_id)
        except NegocioError as exc:
            QMessageBox.warning(self._ventana_padre, "Ficha de la planta", str(exc))
            return

        ficha = FichaPlantaDialog(
            describir_planta(planta),
            filas_historial_estados(cambios),
            filas_historial_consecutivos(consecutivos),
            self._ventana_padre,
        )
        self._planta, self._ficha = planta, ficha
        self._ver_anulados = self._ver_mantenimientos_anulados = False
        if planta.estado.es_final:
            for pestana, que in [
                (ficha.gastos, "gastos"),
                (ficha.mantenimientos, "mantenimientos"),
            ]:
                pestana.deshabilitar_registro(
                    f"La planta está en estado '{planta.estado.etiqueta}': sus {que} se pueden "
                    f"consultar y anular, pero no se registran {que} nuevos."
                )
        ficha.gastos.registrar_solicitado.connect(self.registrar_gasto)
        ficha.gastos.anular_solicitado.connect(self.anular_gasto)
        ficha.gastos.mostrar_anulados_cambiado.connect(self._cambiar_ver_anulados)
        ficha.mantenimientos.registrar_solicitado.connect(self.registrar_mantenimiento)
        ficha.mantenimientos.anular_solicitado.connect(self.anular_mantenimiento)
        ficha.mantenimientos.mostrar_anulados_cambiado.connect(
            self._cambiar_ver_mantenimientos_anulados
        )
        self._recargar_gastos()
        self._recargar_mantenimientos()
        ficha.mostrar_pestana(pestana)
        ficha.exec()
        ficha.deleteLater()
        self._planta, self._ficha = None, None

    # ------------------------------------------------------------------ #
    # Gastos
    # ------------------------------------------------------------------ #

    def registrar_gasto(self) -> None:
        if self._planta is None or self._ficha is None:
            return
        with self._capturar_errores("Registrar gasto"):
            dialogo = RegistrarGastoDialog(
                describir_planta(self._planta),
                [(c.nombre, c.id) for c in self._gastos.listar_categorias()],
                self._sugerencias_descripcion(),
                UNIDADES,
                self._ficha,
            )
            dialogo.set_facturas(self._opciones_facturas())
            dialogo.nueva_factura_solicitada.connect(lambda: self._crear_factura(dialogo))
            dialogo.guardar_solicitado.connect(
                lambda valores: self._guardar(dialogo, lambda: self._registrar(valores))
            )
            if self._ejecutar(dialogo):
                self._recargar_gastos()

    def anular_gasto(self, gasto_id: int) -> None:
        if self._ficha is None:
            return
        vista = self._ficha.gastos
        motivo = vista.pedir_motivo(
            "Anular gasto",
            "Motivo de la anulación (el gasto quedará tachado, no se borra):",
        )
        if motivo is None:
            return
        with self._capturar_errores("Anular gasto"):
            self._gastos.anular_gasto(gasto_id, motivo)
            self._recargar_gastos()

    # ------------------------------------------------------------------ #
    # Mantenimientos
    # ------------------------------------------------------------------ #

    def registrar_mantenimiento(self) -> None:
        if self._planta is None or self._ficha is None:
            return
        with self._capturar_errores("Registrar mantenimiento", self._ficha.mantenimientos):
            planta = self._plantas.obtener(self._planta.id)  # Horómetro al día
            dialogo = RegistrarMantenimientoDialog(
                describir_planta(planta),
                formatear_entero(planta.horometro_actual, "h"),
                TIPOS_MANTENIMIENTO,
                self._mantenimientos.tecnicos(),
                [(c.nombre, c.id) for c in self._gastos.listar_categorias()],
                self._insumos_de_la_ficha(planta),
                UNIDADES,
                sugeridor=lambda fecha, horas: self._mantenimientos.proximo_sugerido(
                    fecha, horas, self._intervalo_meses, self._intervalo_horas
                ),
                parent=self._ficha,
            )
            dialogo.set_facturas(self._opciones_facturas())
            dialogo.nueva_factura_solicitada.connect(lambda: self._crear_factura(dialogo))
            dialogo.guardar_solicitado.connect(
                lambda valores: self._guardar(dialogo, lambda: self._registrar_mant(valores))
            )
            if self._ejecutar(dialogo):
                self._recargar_mantenimientos()
                self._recargar_gastos()  # Sus insumos aparecen también como gastos

    def anular_mantenimiento(self, mantenimiento_id: int) -> None:
        if self._ficha is None:
            return
        vista = self._ficha.mantenimientos
        motivo = vista.pedir_motivo(
            "Anular mantenimiento",
            "Motivo de la anulación (también se anularán sus gastos y su lectura dejará "
            "de contar):",
        )
        if motivo is None:
            return
        with self._capturar_errores("Anular mantenimiento", vista):
            self._mantenimientos.anular(mantenimiento_id, motivo)
            self._recargar_mantenimientos()
            self._recargar_gastos()

    def _registrar_mant(self, valores: dict[str, Any]) -> None:
        if self._planta is None:
            return
        self._mantenimientos.registrar(
            self._planta.id,
            DatosMantenimiento(
                fecha=valores["fecha"],
                tipo=TipoMantenimiento(valores["tipo"]),
                horometro=valores["horometro"],
                descripcion=valores["descripcion"],
                tecnico=valores["tecnico"],
                proxima_fecha=valores["proxima_fecha"],
                proximo_horometro=valores["proximo_horometro"],
            ),
            [
                LineaInsumo(
                    categoria_id=linea["categoria_id"],
                    descripcion=linea["descripcion"],
                    valor_total=linea["valor_total"],
                    cantidad=linea["cantidad"],
                    unidad=linea["unidad"],
                )
                for linea in valores["insumos"]
            ],
            valores["factura_id"],
        )

    def _recargar_mantenimientos(self) -> None:
        if self._planta is None or self._ficha is None:
            return
        vista = self._ficha.mantenimientos
        with self._capturar_errores("Cargar mantenimientos", vista):
            lista = self._mantenimientos.listar(self._planta.id, self._ver_mantenimientos_anulados)
            vista.mostrar_filas([_fila_mantenimiento(m) for m in lista])
            vigentes = [m for m in lista if not m.anulado]
            if not vigentes:
                vista.mostrar_resumen("Esta planta no tiene mantenimientos registrados.")
                return
            ultimo = vigentes[0]
            texto = (
                f"Último: {ultimo.datos.fecha.strftime(FORMATO_FECHA)} a "
                f"{formatear_entero(ultimo.datos.horometro, 'h')} "
                f"({ultimo.datos.tipo.etiqueta.lower()})"
            )
            proximo = _texto_proximo(ultimo)
            if proximo != "—":
                texto += f" · Próximo: {proximo}"
            invertido = sum(m.costo_total for m in vigentes)
            texto += (
                f" · Invertido: {formatear_moneda(invertido)} en {len(vigentes)} mantenimiento(s)"
            )
            vista.mostrar_resumen(texto)

    def _cambiar_ver_mantenimientos_anulados(self, ver: bool) -> None:
        self._ver_mantenimientos_anulados = ver
        self._recargar_mantenimientos()

    def _insumos_de_la_ficha(self, planta: Planta) -> list[InsumoSugerido]:
        """Los filtros y el aceite de la ficha técnica, listos para cargar como líneas."""
        categorias = {c.nombre: c.id for c in self._gastos.listar_categorias()}
        datos = planta.datos
        insumos: list[InsumoSugerido] = []
        if "Filtros" in categorias:
            for nombre, referencia in [
                ("Filtro de aceite", datos.filtro_aceite),
                ("Filtro de combustible", datos.filtro_combustible),
                ("Filtro de agua", datos.filtro_agua),
                ("Filtro de aire", datos.filtro_aire),
            ]:
                if referencia:
                    insumos.append((categorias["Filtros"], f"{nombre} {referencia}", 1.0, "Unidad"))
        if datos.tipo_aceite and "Aceite y lubricantes" in categorias:
            insumos.append(
                (
                    categorias["Aceite y lubricantes"],
                    f"Aceite {datos.tipo_aceite.etiqueta}",
                    datos.cantidad_aceite_gal or 1.0,
                    "Galón",
                )
            )
        return insumos

    # ------------------------------------------------------------------ #
    # Facturas y proveedores
    # ------------------------------------------------------------------ #

    def _crear_factura(self, dialogo_gasto: _ConFacturas) -> None:
        resultado: dict[str, Any] = {}
        dialogo = NuevaFacturaDialog(dialogo_gasto)  # type: ignore[arg-type]
        dialogo.set_proveedores(self._opciones_proveedores())
        dialogo.nuevo_proveedor_solicitado.connect(lambda: self._crear_proveedor(dialogo))
        dialogo.guardar_solicitado.connect(
            lambda valores: self._guardar(
                dialogo, lambda: resultado.update(factura=self._registrar_factura(valores))
            )
        )
        if self._ejecutar(dialogo) and "factura" in resultado:
            # La factura recién creada queda seleccionada en el gasto.
            dialogo_gasto.set_facturas(self._opciones_facturas(), resultado["factura"].id)

    def _crear_proveedor(self, dialogo_factura: NuevaFacturaDialog) -> None:
        resultado: dict[str, Any] = {}
        dialogo = NuevoProveedorDialog(dialogo_factura)
        dialogo.guardar_solicitado.connect(
            lambda valores: self._guardar(
                dialogo,
                lambda: resultado.update(
                    proveedor=self._gastos.registrar_proveedor(
                        valores["nombre"], valores["nit"], valores["telefono"]
                    )
                ),
            )
        )
        if self._ejecutar(dialogo) and "proveedor" in resultado:
            dialogo_factura.set_proveedores(self._opciones_proveedores(), resultado["proveedor"].id)

    # ------------------------------------------------------------------ #
    # Internos
    # ------------------------------------------------------------------ #

    def _registrar(self, valores: dict[str, Any]) -> None:
        if self._planta is None:  # La ficha se cerró: no hay planta a la cual asignar
            return
        self._gastos.registrar_gasto(
            self._planta.id,
            DatosGasto(
                categoria_id=valores["categoria_id"],
                fecha=valores["fecha"],
                descripcion=valores["descripcion"],
                valor_total=valores["valor_total"],
                cantidad=valores["cantidad"],
                unidad=valores["unidad"],
                factura_id=valores["factura_id"],
            ),
        )

    def _registrar_factura(self, valores: dict[str, Any]) -> FacturaProveedor:
        return self._gastos.registrar_factura(
            DatosFactura(
                proveedor_id=valores["proveedor_id"],
                numero_factura=valores["numero_factura"],
                fecha_factura=valores["fecha_factura"],
                valor_total=valores["valor_total"],
                observaciones=valores["observaciones"],
            )
        )

    @staticmethod
    def _guardar(dialogo: FormularioBase, accion: Callable[[], None]) -> None:
        """Ejecuta la acción; si hay errores, el formulario sigue abierto para corregir."""
        try:
            accion()
        except ValidacionError as exc:
            dialogo.marcar_errores(exc.errores)
            return
        except NegocioError as exc:
            dialogo.mostrar_error(str(exc))
            return
        except Exception:
            logger.exception("Error inesperado al guardar desde %s.", dialogo.windowTitle())
            dialogo.mostrar_error(_ERROR_INESPERADO)
            return
        dialogo.accept()

    def _recargar_gastos(self) -> None:
        if self._planta is None or self._ficha is None:
            return
        with self._capturar_errores("Cargar gastos"):
            detalles = self._gastos.listar_gastos(self._planta.id, self._ver_anulados)
            resumen = self._gastos.resumen(self._planta.id)
            self._ficha.gastos.mostrar_gastos([_fila(d) for d in detalles])
            if resumen.cantidad == 0:
                texto = "Esta planta no tiene gastos registrados."
            else:
                categorias = " · ".join(
                    f"{nombre} {formatear_moneda(total)}" for nombre, total in resumen.por_categoria
                )
                texto = (
                    f"Total: {formatear_moneda(resumen.total)} en {resumen.cantidad} "
                    f"gasto(s) · {categorias}"
                )
                if resumen.sin_soporte:
                    texto += f" · Sin soporte: {formatear_moneda(resumen.sin_soporte)}"
            self._ficha.gastos.mostrar_resumen(texto)

    def _cambiar_ver_anulados(self, ver: bool) -> None:
        self._ver_anulados = ver
        self._recargar_gastos()

    def _sugerencias_descripcion(self) -> dict[int, list[str]]:
        """
        Las referencias de la ficha técnica se ofrecen como descripciones:
        el dato que la empresa pidió registrar empieza a trabajar para ella.
        """
        if self._planta is None:
            return {}
        datos = self._planta.datos
        filtros = [
            f"{nombre} {referencia}"
            for nombre, referencia in [
                ("Filtro de aceite", datos.filtro_aceite),
                ("Filtro de combustible", datos.filtro_combustible),
                ("Filtro de agua", datos.filtro_agua),
                ("Filtro de aire", datos.filtro_aire),
            ]
            if referencia
        ]
        aceite = []
        if datos.tipo_aceite:
            cantidad = (
                f" ({formatear_decimal(datos.cantidad_aceite_gal, 'gal')})"
                if datos.cantidad_aceite_gal
                else ""
            )
            aceite.append(f"Aceite {datos.tipo_aceite.etiqueta}{cantidad}")
        por_nombre = {"Filtros": filtros, "Aceite y lubricantes": aceite}
        return {
            c.id: por_nombre[c.nombre]
            for c in self._gastos.listar_categorias()
            if c.nombre in por_nombre
        }

    def _opciones_facturas(self) -> list[OpcionFactura]:
        return [
            OpcionFactura(
                f.id,
                f"{f.datos.numero_factura} · {f.proveedor_nombre}",
                formatear_moneda(f.saldo_por_asignar),
            )
            for f in self._gastos.facturas_con_saldo()
        ]

    def _opciones_proveedores(self) -> list[tuple[str, int]]:
        return [(p.nombre, p.id) for p in self._gastos.listar_proveedores()]

    @staticmethod
    def _ejecutar(dialogo: QDialog) -> bool:
        aceptado = dialogo.exec() == QDialog.DialogCode.Accepted
        dialogo.deleteLater()
        return aceptado

    @contextmanager
    def _capturar_errores(self, accion: str, vista: Any = None) -> Iterator[None]:
        if vista is None and self._ficha is not None:
            vista = self._ficha.gastos
        try:
            yield
        except NegocioError as exc:
            if vista is not None:
                vista.mostrar_error(accion, str(exc))
        except Exception:
            logger.exception("Error inesperado en la acción: %s", accion)
            if vista is not None:
                vista.mostrar_error(accion, _ERROR_INESPERADO)


def _fila(detalle: GastoDetalle) -> FilaGasto:
    """GastoDetalle -> textos de la tabla."""
    gasto, datos = detalle.gasto, detalle.gasto.datos
    cantidad = formatear_decimal(datos.cantidad)
    if datos.unidad:
        cantidad += f" {datos.unidad}"
    soporte = (
        f"{detalle.numero_factura} · {detalle.proveedor}"
        if detalle.tiene_soporte
        else "Sin soporte"
    )
    descripcion = datos.descripcion
    if detalle.mantenimiento_fecha is not None:
        descripcion += f" (mantenimiento {detalle.mantenimiento_fecha.strftime(FORMATO_FECHA)})"
    return FilaGasto(
        id=gasto.id,
        fecha=datos.fecha.strftime(FORMATO_FECHA),
        categoria=detalle.categoria,
        descripcion=descripcion,
        cantidad=cantidad,
        valor=formatear_moneda(datos.valor_total),
        soporte=soporte,
        anulado=gasto.anulado,
        motivo_anulacion=gasto.motivo_anulacion,
    )


def _texto_proximo(mantenimiento: Mantenimiento) -> str:
    """Ej. "09/04/2027 o 2.325 h" (lo que ocurra primero)."""
    partes = []
    if mantenimiento.datos.proxima_fecha:
        partes.append(mantenimiento.datos.proxima_fecha.strftime(FORMATO_FECHA))
    if mantenimiento.datos.proximo_horometro:
        partes.append(formatear_entero(mantenimiento.datos.proximo_horometro, "h"))
    return " o ".join(partes) or "—"


def _fila_mantenimiento(mantenimiento: Mantenimiento) -> FilaRegistro:
    datos = mantenimiento.datos
    return FilaRegistro(
        mantenimiento.id,
        (
            datos.fecha.strftime(FORMATO_FECHA),
            datos.tipo.etiqueta,
            formatear_entero(datos.horometro, "h"),
            datos.tecnico or "—",
            datos.descripcion,
            formatear_moneda(mantenimiento.costo_total) if mantenimiento.costo_total else "—",
            _texto_proximo(mantenimiento),
        ),
        mantenimiento.anulado,
        mantenimiento.motivo_anulacion,
    )
