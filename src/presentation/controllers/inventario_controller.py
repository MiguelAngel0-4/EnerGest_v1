"""
Controlador de la pantalla de inventario.

Ruta: src/presentation/controllers/inventario_controller.py

Es el "maître" del restaurante: recibe los pedidos del mesero (las
señales de la vista), los lleva a la cocina (PlantaService) y le indica
al mesero qué servir (tabla actualizada, mensajes o errores).

No contiene SQL ni reglas de negocio: solo coordina y traduce entre
el lenguaje de la interfaz y el de los servicios.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from typing import Any, Final

from PySide6.QtCore import QModelIndex, QObject
from PySide6.QtWidgets import QDialog

from src.business.exceptions import NegocioError, ValidacionError
from src.business.models.estado_planta import EstadoPlanta
from src.business.models.planta import Planta, TipoCombustible
from src.business.services.planta_service import PlantaService
from src.presentation.controllers.planta_form_mapper import datos_a_valores, valores_a_datos
from src.presentation.dialogs.cambiar_estado_dialog import CambiarEstadoDialog, OpcionEstado
from src.presentation.dialogs.historial_planta_dialog import HistorialPlantaDialog
from src.presentation.dialogs.planta_form_dialog import PlantaFormDialog
from src.presentation.table_models.plantas_table_model import (
    ID_ROLE,
    RANGOS_POTENCIA,
    Columna,
    PlantasFilterProxy,
    PlantasTableModel,
)
from src.presentation.views.equipos.inventario_view import InventarioView
from src.presentation.widgets.acciones_delegate import AccionesDelegate
from src.shared.formatters import formatear_consecutivo

logger = logging.getLogger(__name__)

# Claves especiales del filtro de estado.
_EN_OPERACION: Final[str] = "EN_OPERACION"
_TODOS: Final[str] = "TODOS"

_VOLTAJES_SUGERIDOS: Final[list[str]] = [
    "120 V",
    "120/240 V",
    "208 V",
    "220 V",
    "220/440 V",
    "440 V",
]
_OPCIONES_FASES: Final[list[tuple[str, int | None]]] = [
    ("—", None),
    ("Monofásica (1)", 1),
    ("Trifásica (3)", 3),
]
_FORMATO_FECHA: Final[str] = "%d/%m/%Y"

_ACCIONES: Final[list[tuple[str, str]]] = [
    ("editar", "Editar"),
    ("estado", "Estado"),
    ("historial", "Historial"),
]


class InventarioController(QObject):
    """Coordina la vista de inventario con el servicio de plantas."""

    def __init__(
        self, servicio: PlantaService, vista: InventarioView, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._servicio = servicio
        self._vista = vista
        # Planta devuelta por la última operación exitosa de un diálogo.
        self._resultado: Planta | None = None

        # Cadena de datos: modelo (todas las cargadas) -> proxy (filtra/ordena) -> tabla.
        self._modelo = PlantasTableModel(self)
        self._proxy = PlantasFilterProxy(self)
        self._proxy.setSourceModel(self._modelo)
        self._delegado = AccionesDelegate(_ACCIONES, ID_ROLE, self)
        self._vista.set_modelo(
            self._proxy,
            anchos_fijos={
                Columna.CONSECUTIVO: 100,
                Columna.POTENCIA: 80,
                Columna.SERIAL: 100,
                Columna.HOROMETRO: 95,
                Columna.ESTADO: 150,
                Columna.ACCIONES: self._delegado.ancho_requerido(),
            },
            columnas_flexibles=[Columna.MARCA, Columna.MODELO],
        )
        self._vista.set_delegado_acciones(self._delegado, Columna.ACCIONES)

        self._configurar_filtros()
        self._conectar_senales()

    # ------------------------------------------------------------------ #
    # Configuración
    # ------------------------------------------------------------------ #

    def _configurar_filtros(self) -> None:
        opciones_estado: list[tuple[str, str | None]] = [
            ("En operación", _EN_OPERACION),
            ("Todos los estados", _TODOS),
        ]
        opciones_estado += [(e.etiqueta, e.value) for e in EstadoPlanta]
        self._vista.set_opciones_combo("estado", opciones_estado, conservar=False)

        opciones_potencia: list[tuple[str, str | None]] = [("Todas las potencias", None)]
        opciones_potencia += [(datos[0], clave) for clave, datos in RANGOS_POTENCIA.items()]
        self._vista.set_opciones_combo("potencia", opciones_potencia, conservar=False)

        self._vista.set_opciones_combo("marca", [("Todas las marcas", None)], conservar=False)

    def _conectar_senales(self) -> None:
        self._vista.busqueda_cambiada.connect(lambda _texto: self.recargar())
        self._vista.filtros_cambiados.connect(self._aplicar_filtros_locales)
        self._vista.registro_solicitado.connect(self.abrir_registro)
        self._vista.fila_activada.connect(self._al_activar_fila)
        self._vista.numero_consultado.connect(self.consultar_numero)
        self._delegado.accion_solicitada.connect(self._al_solicitar_accion)

    # ------------------------------------------------------------------ #
    # Casos de uso de la pantalla
    # ------------------------------------------------------------------ #

    def recargar(self) -> None:
        """Consulta el servicio y actualiza tabla, filtros y panel de números."""
        with self._capturar_errores("Cargar inventario"):
            # Se cargan TODAS (incluidas las fuera de operación); el filtro de
            # estado se aplica en memoria con el proxy, sin volver a consultar.
            plantas = self._servicio.listar(
                incluir_fuera_de_operacion=True, texto=self._vista.texto_busqueda()
            )
            self._modelo.cargar(plantas)
            self._actualizar_opciones_marca()
            self._aplicar_filtros_locales()
            self._actualizar_panel_numeros()

    def abrir_registro(self) -> None:
        """Formulario de registro: la planta recibe automáticamente el menor número libre."""
        with self._capturar_errores("Registrar nueva planta"):
            proximo = formatear_consecutivo(self._servicio.proximo_numero())
            dialogo = self._crear_formulario(
                "Registrar nueva planta",
                f"Se asignará automáticamente: {proximo}",
                f"{EstadoPlanta.DISPONIBLE.etiqueta} (automático)",
            )
            dialogo.guardar_solicitado.connect(
                lambda valores: self._guardar(dialogo, valores, planta_id=None)
            )
            if self._ejecutar(dialogo) and self._resultado is not None:
                planta = self._resultado
                self.recargar()
                self._vista.mostrar_info(
                    "Planta registrada",
                    f"{self._describir(planta)}\n\nQuedó registrada con el número "
                    f"{formatear_consecutivo(planta.numero_consecutivo)}.",
                )

    def editar(self, planta_id: int) -> None:
        """Formulario de edición de datos técnicos (estado y número no se editan aquí)."""
        with self._capturar_errores("Editar planta"):
            planta = self._servicio.obtener(planta_id)
            dialogo = self._crear_formulario(
                f"Editar planta {formatear_consecutivo(planta.numero_consecutivo)}",
                f"{formatear_consecutivo(planta.numero_consecutivo)} (no editable)",
                f"{planta.estado.etiqueta} (se cambia con el botón Estado)",
            )
            dialogo.cargar_valores(datos_a_valores(planta.datos))
            dialogo.guardar_solicitado.connect(
                lambda valores: self._guardar(dialogo, valores, planta_id=planta_id)
            )
            if self._ejecutar(dialogo):
                self.recargar()

    def cambiar_estado(self, planta_id: int) -> None:
        """Diálogo de cambio de estado con solo las transiciones válidas."""
        with self._capturar_errores("Cambiar estado"):
            planta = self._servicio.obtener(planta_id)
            if planta.estado.es_final:
                self._vista.mostrar_info(
                    "Estado definitivo",
                    f"La planta está en estado '{planta.estado.etiqueta}', que es definitivo.\n"
                    "Su información se conserva para consulta e historial.",
                )
                return

            cambios, _ = self._servicio.historial(planta_id)
            fecha_minima = cambios[-1].fecha if cambios else planta.fecha_registro.date()
            opciones = [
                OpcionEstado(
                    clave=destino.value,
                    etiqueta=destino.etiqueta,
                    requiere_motivo=destino.requiere_motivo,
                    aviso=self._aviso_transicion(planta, destino),
                )
                for destino in EstadoPlanta  # Recorre en el orden del Enum
                if planta.estado.puede_pasar_a(destino)
            ]
            dialogo = CambiarEstadoDialog(
                self._describir(planta), planta.estado.etiqueta, opciones, fecha_minima, self._vista
            )
            dialogo.cambio_solicitado.connect(
                lambda clave, motivo, fecha: self._aplicar_cambio_estado(
                    dialogo, planta, clave, motivo, fecha
                )
            )
            if self._ejecutar(dialogo) and self._resultado is not None:
                actualizada = self._resultado
                self.recargar()
                self._vista.mostrar_info(
                    "Estado actualizado", self._resumen_cambio(planta, actualizada)
                )

    def ver_historial(self, planta_id: int) -> None:
        """Muestra la línea de tiempo de estados y de números consecutivos."""
        with self._capturar_errores("Ver historial"):
            planta = self._servicio.obtener(planta_id)
            cambios, consecutivos = self._servicio.historial(planta_id)
            filas_estados = [
                (
                    c.fecha.strftime(_FORMATO_FECHA),
                    c.estado_anterior.etiqueta if c.estado_anterior else "— (registro)",
                    c.estado_nuevo.etiqueta,
                    c.motivo or "",
                )
                for c in cambios
            ]
            filas_consecutivos = [
                (
                    formatear_consecutivo(r.numero),
                    r.fecha_asignacion.strftime(_FORMATO_FECHA),
                    r.fecha_liberacion.strftime(_FORMATO_FECHA) if r.fecha_liberacion else "Vigente",
                    r.motivo_liberacion or "",
                )
                for r in consecutivos
            ]
            dialogo = HistorialPlantaDialog(
                self._describir(planta), filas_estados, filas_consecutivos, self._vista
            )
            self._ejecutar(dialogo)

    def consultar_numero(self, numero: int) -> None:
        """Muestra qué plantas han tenido un número consecutivo."""
        etiqueta = formatear_consecutivo(numero)
        with self._capturar_errores(f"Consultar el número {etiqueta}"):
            registros = self._servicio.quienes_tuvieron_numero(numero)
            if not registros:
                self._vista.mostrar_info(etiqueta, f"El número {etiqueta} no ha sido asignado.")
                return

            lineas: list[str] = []
            for registro in registros:
                datos = self._servicio.obtener(registro.planta_id).datos
                descripcion = " ".join(filter(None, [datos.marca, datos.modelo]))
                serie = datos.numero_serie or "sin serial"
                periodo = f"desde {registro.fecha_asignacion:%d/%m/%Y}"
                if registro.fecha_liberacion is not None:
                    periodo += f" hasta {registro.fecha_liberacion:%d/%m/%Y}"
                    periodo += f" ({registro.motivo_liberacion})"
                else:
                    periodo += " (vigente)"
                lineas.append(f"• {descripcion} — {serie}\n   {periodo}")

            self._vista.mostrar_info(
                f"Historial del número {etiqueta}",
                f"Plantas que han tenido el número {etiqueta}:\n\n" + "\n\n".join(lineas),
            )

    # ------------------------------------------------------------------ #
    # Métodos internos
    # ------------------------------------------------------------------ #

    def _crear_formulario(
        self, titulo: str, texto_consecutivo: str, texto_estado: str
    ) -> PlantaFormDialog:
        """Crea el formulario con las opciones de los combos."""
        marcas = sorted(
            {p.datos.marca for p in self._servicio.listar(incluir_fuera_de_operacion=True)},
            key=str.casefold,
        )
        combustibles: list[tuple[str, str | None]] = [("—", None)]
        combustibles += [(c.etiqueta, c.value) for c in TipoCombustible]
        return PlantaFormDialog(
            titulo,
            texto_consecutivo,
            texto_estado,
            marcas,
            _OPCIONES_FASES,
            combustibles,
            _VOLTAJES_SUGERIDOS,
            self._vista,
        )

    def _guardar(
        self, dialogo: PlantaFormDialog, valores: dict[str, Any], planta_id: int | None
    ) -> None:
        """Respuesta al botón Guardar: registra o actualiza, o marca los errores."""
        try:
            datos = valores_a_datos(valores)
            if planta_id is None:
                self._resultado = self._servicio.registrar(datos)
            else:
                self._resultado = self._servicio.actualizar_datos(planta_id, datos)
        except ValidacionError as exc:
            dialogo.marcar_errores(exc.errores)  # El diálogo sigue abierto para corregir
            return
        except NegocioError as exc:
            dialogo.mostrar_error(str(exc))
            return
        except Exception:
            logger.exception("Error inesperado al guardar la planta.")
            dialogo.mostrar_error(
                "Ocurrió un error inesperado. Los detalles quedaron registrados en el log."
            )
            return
        dialogo.accept()

    def _aplicar_cambio_estado(
        self,
        dialogo: CambiarEstadoDialog,
        planta: Planta,
        clave: str,
        motivo: str,
        fecha: date,
    ) -> None:
        """Respuesta al botón Actualizar estado."""
        nuevo = EstadoPlanta(clave)
        # Se revisa el motivo ANTES de confirmar: sería frustrante aceptar una acción
        # "irreversible" y recibir después el error de que faltaba el motivo.
        # La regla sigue viviendo en el negocio (EstadoPlanta.requiere_motivo).
        if nuevo.requiere_motivo and not motivo.strip():
            dialogo.mostrar_errores(
                {"motivo": f"Debe indicar el motivo para pasar a '{nuevo.etiqueta}'."}
            )
            return
        if nuevo.es_final and not dialogo.confirmar(
            "Confirmar cambio definitivo",
            f"¿Confirma que la planta {self._describir(planta)} pasa a '{nuevo.etiqueta}'?\n\n"
            "Este estado es definitivo y no se puede revertir.",
        ):
            return
        try:
            self._resultado = self._servicio.cambiar_estado(planta.id, nuevo, motivo, fecha)
        except ValidacionError as exc:
            dialogo.mostrar_errores(exc.errores)
            return
        except NegocioError as exc:
            dialogo.mostrar_error(str(exc))
            return
        except Exception:
            logger.exception("Error inesperado al cambiar el estado.")
            dialogo.mostrar_error(
                "Ocurrió un error inesperado. Los detalles quedaron registrados en el log."
            )
            return
        dialogo.accept()

    def _ejecutar(self, dialogo: QDialog) -> bool:
        """Abre un diálogo modal, lo libera de memoria al cerrarse e indica si se aceptó."""
        self._resultado = None
        aceptado = dialogo.exec() == QDialog.DialogCode.Accepted
        dialogo.deleteLater()
        return aceptado

    @staticmethod
    def _describir(planta: Planta) -> str:
        """Ej. "PE-005 · Cummins C50D6"."""
        numero = (
            formatear_consecutivo(planta.numero_consecutivo)
            if planta.numero_consecutivo is not None
            else "Sin número"
        )
        nombre = " ".join(filter(None, [planta.datos.marca, planta.datos.modelo]))
        return f"{numero} · {nombre}"

    @staticmethod
    def _aviso_transicion(planta: Planta, destino: EstadoPlanta) -> str:
        """Explica al usuario las consecuencias del cambio antes de confirmarlo."""
        avisos: list[str] = []
        if planta.estado.en_operacion and not destino.en_operacion:
            numero = formatear_consecutivo(planta.numero_consecutivo)
            avisos.append(
                f"La planta liberará el número {numero}, que quedará disponible "
                "para la próxima planta registrada."
            )
        elif not planta.estado.en_operacion and destino.en_operacion:
            avisos.append(
                "La planta volverá a operar y recibirá un número consecutivo: "
                "el que tenía antes, si sigue libre; si no, el menor disponible."
            )
        if destino.es_final:
            avisos.append("Este estado es definitivo.")
        return " ".join(avisos)

    @staticmethod
    def _resumen_cambio(antes: Planta, despues: Planta) -> str:
        """Mensaje de confirmación tras un cambio de estado."""
        texto = (
            f"{InventarioController._describir(antes)}\n\n"
            f"Pasó de '{antes.estado.etiqueta}' a '{despues.estado.etiqueta}'."
        )
        if antes.numero_consecutivo is not None and despues.numero_consecutivo is None:
            texto += f"\nEl número {formatear_consecutivo(antes.numero_consecutivo)} quedó libre."
        elif antes.numero_consecutivo is None and despues.numero_consecutivo is not None:
            texto += (
                f"\nRecibió el número {formatear_consecutivo(despues.numero_consecutivo)}."
            )
        return texto

    def _aplicar_filtros_locales(self) -> None:
        """Traduce las opciones de los combos a filtros del proxy."""
        clave_estado = self._vista.valor_filtro("estado")
        if clave_estado == _EN_OPERACION:
            estados: set[str] | None = {e.value for e in EstadoPlanta if e.en_operacion}
        elif clave_estado == _TODOS or clave_estado is None:
            estados = None
        else:
            estados = {clave_estado}

        clave_potencia = self._vista.valor_filtro("potencia")
        rango = None
        if clave_potencia in RANGOS_POTENCIA:
            _texto, minimo, maximo = RANGOS_POTENCIA[clave_potencia]
            rango = (minimo, maximo)

        self._proxy.filtrar(estados, self._vista.valor_filtro("marca"), rango)
        self._vista.mostrar_resumen(
            f"Mostrando {self._proxy.rowCount()} de {self._modelo.rowCount()} plantas"
        )

    def _actualizar_opciones_marca(self) -> None:
        """Llena el combo de marcas con las marcas presentes, sin duplicados."""
        marcas: dict[str, str] = {}
        for planta in self._modelo.plantas:
            marcas.setdefault(planta.datos.marca.casefold(), planta.datos.marca)
        opciones: list[tuple[str, str | None]] = [("Todas las marcas", None)]
        opciones += [(marca, marca) for marca in sorted(marcas.values(), key=str.casefold)]
        self._vista.set_opciones_combo("marca", opciones)

    def _actualizar_panel_numeros(self) -> None:
        libres = self._servicio.numeros_libres()
        proximo = self._servicio.proximo_numero()
        self._vista.mostrar_numeros_libres(
            [(formatear_consecutivo(n), n) for n in libres], formatear_consecutivo(proximo)
        )

    def _al_solicitar_accion(self, accion: str, planta_id: int) -> None:
        manejadores = {
            "editar": self.editar,
            "estado": self.cambiar_estado,
            "historial": self.ver_historial,
        }
        manejadores[accion](planta_id)

    def _al_activar_fila(self, indice: QModelIndex) -> None:
        """Doble clic en una fila = editar."""
        planta_id = indice.data(ID_ROLE)
        if planta_id is not None:
            self.editar(int(planta_id))

    @contextmanager
    def _capturar_errores(self, accion: str) -> Iterator[None]:
        """
        Red de seguridad para cada acción del usuario:
        - Errores de negocio: se muestran tal cual (ya vienen redactados para el usuario).
        - Errores inesperados: se registran completos en el log y se muestra un aviso genérico.
        """
        try:
            yield
        except NegocioError as exc:
            self._vista.mostrar_error(accion, str(exc))
        except Exception:
            logger.exception("Error inesperado en la acción: %s", accion)
            self._vista.mostrar_error(
                accion,
                "Ocurrió un error inesperado. Los detalles quedaron registrados en el log.",
            )
