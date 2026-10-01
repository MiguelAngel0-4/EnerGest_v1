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
from typing import Final

from PySide6.QtCore import QModelIndex, QObject

from src.business.exceptions import NegocioError
from src.business.models.estado_planta import EstadoPlanta
from src.business.services.planta_service import PlantaService
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
        """Abre el formulario de registro (se implementa en la Entrega D)."""
        self._funcion_pendiente("Registrar nueva planta")

    def editar(self, planta_id: int) -> None:
        """Abre el formulario de edición (se implementa en la Entrega D)."""
        self._funcion_pendiente(f"Editar planta id={planta_id}")

    def cambiar_estado(self, planta_id: int) -> None:
        """Abre el diálogo de cambio de estado (se implementa en la Entrega D)."""
        self._funcion_pendiente(f"Cambiar estado de la planta id={planta_id}")

    def ver_historial(self, planta_id: int) -> None:
        """Abre el diálogo de historial (se implementa en la Entrega D)."""
        self._funcion_pendiente(f"Historial de la planta id={planta_id}")

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

    def _funcion_pendiente(self, accion: str) -> None:
        logger.info("Acción solicitada aún no disponible: %s", accion)
        self._vista.mostrar_info(
            "Próximamente", f"{accion}.\n\nEsta función se incorpora en la siguiente entrega."
        )

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
