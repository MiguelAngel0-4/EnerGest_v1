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
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any, Final

from PySide6.QtCore import QModelIndex, QObject, QSettings, QStandardPaths
from PySide6.QtWidgets import QDialog

from src.business.exceptions import NegocioError, ValidacionError
from src.business.models.comercial import DatosContrato, DatosVenta, ModalidadAlquiler
from src.business.models.estado_planta import EstadoPlanta
from src.business.models.mantenimiento import AlertaMantenimiento, NivelAlerta
from src.business.models.planta import Planta, TipoAceite, TipoCombustible
from src.business.services.comercial_service import ComercialService
from src.business.services.hoja_vida_service import HojaVidaService
from src.business.services.mantenimiento_service import MantenimientoService
from src.business.services.planta_service import PlantaService
from src.presentation.controllers.clientes import crear_cliente_desde, opciones_clientes
from src.presentation.controllers.ficha_controller import FichaPlantaController
from src.presentation.controllers.nombres_archivo import nombre_archivo_hoja_vida
from src.presentation.controllers.planta_form_mapper import datos_a_valores, valores_a_datos
from src.presentation.controllers.textos import describir_planta, texto_liquidacion
from src.presentation.dialogs.cambiar_estado_dialog import (
    CambiarEstadoDialog,
    OpcionEstado,
    VistaLiquidacion,
)
from src.presentation.dialogs.planta_form_dialog import (
    CAMPOS_FILTROS,
    OpcionesFormulario,
    PlantaFormDialog,
)
from src.presentation.table_models.plantas_table_model import (
    ID_ROLE,
    RANGOS_POTENCIA,
    Columna,
    PlantasFilterProxy,
    PlantasTableModel,
)
from src.presentation.views.equipos.inventario_view import InventarioView
from src.presentation.widgets.acciones_delegate import AccionesDelegate
from src.shared.formatters import formatear_consecutivo, formatear_entero, formatear_moneda

_COLOR_ALERTA: Final[dict[NivelAlerta, str]] = {
    NivelAlerta.VENCIDO: "#C0392B",
    NivelAlerta.PROXIMO: "#D35400",
}

logger = logging.getLogger(__name__)

# Claves especiales del filtro de estado.
_EN_OPERACION: Final[str] = "EN_OPERACION"
_TODOS: Final[str] = "TODOS"

# Valor que usa la empresa. El campo admite escribir otro si llega un equipo distinto.
_VOLTAJES_SUGERIDOS: Final[list[str]] = ["110/220 V"]
_OPCIONES_FASES: Final[list[tuple[str, int | None]]] = [
    ("—", None),
    ("Monofásica (1)", 1),
    ("Trifásica (3)", 3),
]

_ACCIONES: Final[list[tuple[str, str]]] = [
    ("editar", "Editar"),
    ("estado", "Estado"),
    ("ficha", "Ficha"),  # Historial y gastos (antes "Historial")
    ("pdf", "PDF"),
]

# Preferencia del usuario: última carpeta donde guardó una hoja de vida.
_CLAVE_CARPETA_HOJAS: Final[str] = "hojas_vida/carpeta"


class InventarioController(QObject):
    """Coordina la vista de inventario con el servicio de plantas."""

    def __init__(
        self,
        servicio: PlantaService,
        hojas_vida: HojaVidaService,
        vista: InventarioView,
        parent: QObject | None = None,
        preferencias: QSettings | None = None,
        ficha: FichaPlantaController | None = None,
        mantenimientos: MantenimientoService | None = None,
        comercial: ComercialService | None = None,
    ) -> None:
        """
        Args:
            preferencias: Dónde recordar ajustes del usuario (por ejemplo, la última
                carpeta usada). Por defecto, el registro de Windows del usuario;
                las pruebas usan un archivo temporal para no tocar el registro.
        """
        super().__init__(parent)
        self._servicio = servicio
        self._hojas_vida = hojas_vida
        self._vista = vista
        self._preferencias = preferencias or QSettings("EnerGest", "EnerGest")
        self._ficha = ficha
        self._mantenimientos = mantenimientos
        self._comercial = comercial
        self._mensaje_comercial = ""
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
                Columna.POTENCIA: 75,
                Columna.SERIAL: 90,
                Columna.HOROMETRO: 95,
                Columna.ESTADO: 145,
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
        self._vista.alerta_seleccionada.connect(
            lambda planta_id: self.ver_ficha(planta_id, "Mantenimientos")
        )
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
            if self._comercial is not None:
                self._modelo.set_clientes_actuales(self._comercial.clientes_actuales())
            self._actualizar_opciones_marca()
            self._aplicar_filtros_locales()
            self._actualizar_panel_numeros()
            self._actualizar_alertas()

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
                combustible_actual=planta.datos.tipo_combustible,
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
            comercial = self._comercial is not None
            contrato = self._comercial.contrato_activo(planta_id) if self._comercial else None
            opciones = [
                OpcionEstado(
                    clave=destino.value,
                    etiqueta=destino.etiqueta,
                    # Al vender, el motivo se completa solo ("Venta a [cliente]").
                    requiere_motivo=destino.requiere_motivo
                    and not (comercial and destino is EstadoPlanta.VENDIDA),
                    aviso=self._aviso_transicion(planta, destino, comercial, contrato is not None),
                    seccion=self._seccion_comercial(destino) if comercial else "",
                    # Obligatoria al salir en alquiler; opcional al regresar de él
                    # (con ambas lecturas se conocen las horas de uso del alquiler).
                    pide_horometro=(
                        destino.requiere_horometro or planta.estado is EstadoPlanta.ALQUILADA
                    ),
                    horometro_obligatorio=destino.requiere_horometro,
                )
                for destino in EstadoPlanta  # Recorre en el orden del Enum
                if planta.estado.puede_pasar_a(destino)
            ]
            dialogo = CambiarEstadoDialog(
                self._describir(planta),
                planta.estado.etiqueta,
                opciones,
                fecha_minima,
                formatear_entero(planta.horometro_actual, "h"),
                self._vista,
                liquidador=self._liquidador(planta_id) if contrato is not None else None,
            )
            if self._comercial is not None:
                comercial_servicio = self._comercial
                dialogo.set_clientes(opciones_clientes(comercial_servicio))
                dialogo.nuevo_cliente_solicitado.connect(
                    lambda: crear_cliente_desde(dialogo, comercial_servicio)
                )
            dialogo.cambio_solicitado.connect(
                lambda clave, motivo, fecha, horometro: self._aplicar_cambio_estado(
                    dialogo, planta, clave, motivo, fecha, horometro
                )
            )
            self._mensaje_comercial = ""
            if self._ejecutar(dialogo) and self._resultado is not None:
                actualizada = self._resultado
                self.recargar()
                resumen = self._resumen_cambio(planta, actualizada)
                if self._mensaje_comercial:
                    resumen += f"\n{self._mensaje_comercial}"
                self._vista.mostrar_info("Estado actualizado", resumen)

    def ver_ficha(self, planta_id: int, pestana: str = "Historial") -> None:
        """Abre la ficha de la planta y, al cerrarla, refresca horómetros y alertas."""
        if self._ficha is None:
            logger.error("No se configuró el controlador de la ficha.")
            return
        self._ficha.abrir(planta_id, pestana)
        self.recargar()

    def generar_hoja_vida(self, planta_id: int) -> None:
        """Pide dónde guardar, genera el PDF y ofrece abrirlo."""
        with self._capturar_errores("Generar hoja de vida"):
            planta = self._servicio.obtener(planta_id)
            numero = planta.numero_consecutivo
            if numero is None:  # Planta fuera de operación: se usa el último número que tuvo
                _, consecutivos = self._servicio.historial(planta_id)
                numero = consecutivos[-1].numero if consecutivos else None
            nombre = nombre_archivo_hoja_vida(
                formatear_consecutivo(numero) if numero is not None else "SIN-NUMERO",
                planta.datos.marca,
                planta.datos.modelo,
                date.today(),
            )

            destino = self._vista.pedir_ruta_guardado(
                "Guardar hoja de vida",
                self._carpeta_hojas_vida() / nombre,
                "Documentos PDF (*.pdf)",
            )
            if destino is None:
                return  # El usuario canceló
            if destino.suffix.lower() != ".pdf":
                destino = destino.with_name(destino.name + ".pdf")

            with self._vista.cursor_espera():
                ruta = self._hojas_vida.exportar(planta_id, destino)
            self._preferencias.setValue(_CLAVE_CARPETA_HOJAS, str(ruta.parent))

            eleccion = self._vista.preguntar_tras_generar(
                "Hoja de vida generada", f"{self._describir(planta)}\n\nSe guardó en:\n{ruta}"
            )
            objetivo = {"abrir": ruta, "carpeta": ruta.parent}.get(eleccion)
            if objetivo is not None and not self._vista.abrir_ruta(objetivo):
                self._vista.mostrar_info(
                    "No se pudo abrir",
                    f"Windows no encontró un programa para abrir:\n{objetivo}",
                )

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
        self,
        titulo: str,
        texto_consecutivo: str,
        texto_estado: str,
        combustible_actual: TipoCombustible | None = None,
    ) -> PlantaFormDialog:
        """
        Crea el formulario con las opciones de los combos.

        Args:
            combustible_actual: Al editar, el combustible que ya tiene la planta.
                Si es uno retirado (Gas), se ofrece como "(histórico)" para que
                el dato no se borre sin querer al guardar.
        """
        todas = self._servicio.listar(incluir_fuera_de_operacion=True)  # Una sola consulta
        marcas = sorted({p.datos.marca for p in todas}, key=str.casefold)
        combustibles: list[tuple[str, str | None]] = [("—", None)]
        combustibles += [(c.etiqueta, c.value) for c in TipoCombustible if c.vigente]
        if combustible_actual is not None and not combustible_actual.vigente:
            combustibles.append(
                (f"{combustible_actual.etiqueta} (histórico)", combustible_actual.value)
            )
        aceites: list[tuple[str, str | None]] = [("—", None)]
        aceites += [(a.etiqueta, a.value) for a in TipoAceite]
        # Referencias de filtros ya usadas: se sugieren para escribirlas igual siempre.
        sugerencias = {
            campo: sorted(
                {getattr(p.datos, campo) for p in todas if getattr(p.datos, campo)},
                key=str.casefold,
            )
            for campo in CAMPOS_FILTROS
        }
        opciones = OpcionesFormulario(
            marcas=marcas,
            opciones_fases=_OPCIONES_FASES,
            opciones_combustible=combustibles,
            opciones_aceite=aceites,
            voltajes=_VOLTAJES_SUGERIDOS,
            sugerencias_filtros=sugerencias,
        )
        return PlantaFormDialog(titulo, texto_consecutivo, texto_estado, opciones, self._vista)

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
        horometro: int | None,
    ) -> None:
        """Respuesta al botón Actualizar estado."""
        nuevo = EstadoPlanta(clave)
        venta_comercial = self._comercial is not None and nuevo is EstadoPlanta.VENDIDA
        # Se revisa el motivo ANTES de confirmar: sería frustrante aceptar una acción
        # "irreversible" y recibir después el error de que faltaba el motivo.
        # La regla sigue viviendo en el negocio (EstadoPlanta.requiere_motivo).
        if nuevo.requiere_motivo and not venta_comercial and not motivo.strip():
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
            self._mensaje_comercial = self._ejecutar_cambio(
                planta, nuevo, motivo, fecha, horometro, dialogo.datos_comerciales()
            )
            self._resultado = self._servicio.obtener(planta.id)
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

    def _carpeta_hojas_vida(self) -> Path:
        """
        Última carpeta usada o, la primera vez, Documentos/EnerGest/Hojas de vida.

        QStandardPaths encuentra la carpeta Documentos real del usuario, aunque
        Windows la haya movido (por ejemplo, a OneDrive).
        """
        guardada = self._preferencias.value(_CLAVE_CARPETA_HOJAS)
        if guardada and Path(str(guardada)).is_dir():
            return Path(str(guardada))
        documentos = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation
        )
        carpeta = Path(documentos or Path.home()) / "EnerGest" / "Hojas de vida"
        try:
            carpeta.mkdir(parents=True, exist_ok=True)
        except OSError:
            logger.warning("No se pudo crear %s; se usa la carpeta personal.", carpeta)
            return Path.home()
        return carpeta

    def _ejecutar(self, dialogo: QDialog) -> bool:
        """Abre un diálogo modal, lo libera de memoria al cerrarse e indica si se aceptó."""
        self._resultado = None
        aceptado = dialogo.exec() == QDialog.DialogCode.Accepted
        dialogo.deleteLater()
        return aceptado

    @staticmethod
    def _describir(planta: Planta) -> str:
        """Ej. "PE-005 · Cummins C50D6" (texto compartido con la ficha)."""
        return describir_planta(planta)

    def _ejecutar_cambio(
        self,
        planta: Planta,
        nuevo: EstadoPlanta,
        motivo: str,
        fecha: date,
        horometro: int | None,
        datos: dict[str, Any],
    ) -> str:
        """
        Enruta el cambio al caso de uso que corresponde: alquilar, vender,
        devolver un alquiler o un cambio de estado simple.

        Returns:
            Texto con el resultado comercial para el mensaje final ("" si no aplica).
        """
        comercial = self._comercial
        if comercial is not None and "contrato" in datos:
            c = datos["contrato"]
            contrato = DatosContrato(
                c["cliente_id"], ModalidadAlquiler(c["modalidad"]), c["tarifa"], c["observaciones"]
            )
            alquiler = comercial.alquilar(planta.id, contrato, horometro, fecha, motivo)  # type: ignore[arg-type]
            return (
                f"Contrato con {alquiler.cliente_nombre}: "
                f"{alquiler.modalidad.etiqueta.lower()} {formatear_moneda(alquiler.tarifa)}."
            )
        elif comercial is not None and "venta" in datos:
            v = datos["venta"]
            venta = DatosVenta(v["cliente_id"], v["valor"], v["numero_documento"])
            ingreso = comercial.vender(planta.id, venta, fecha, motivo)
            return f"Venta a {ingreso.cliente_nombre} por {formatear_moneda(ingreso.datos.valor)}."
        elif comercial is not None and planta.estado is EstadoPlanta.ALQUILADA:
            liquidacion = datos.get("liquidacion", {})
            cerrado = comercial.devolver(
                planta.id,
                nuevo,
                fecha,
                horometro,
                motivo,
                valor_liquidado=liquidacion.get("valor_liquidado"),
                cobrar_saldo=liquidacion.get("cobrar_saldo", False),
                numero_documento=liquidacion.get("numero_documento"),
            )
            if cerrado is None:  # Alquiler anterior a la 0.7.0, sin contrato
                return ""
            texto = (
                f"Liquidación: {formatear_moneda(cerrado.valor_liquidado or 0)} · "
                f"Cobrado: {formatear_moneda(cerrado.cobrado)}"
            )
            if cerrado.saldo:
                texto += f" · Saldo por cobrar: {formatear_moneda(cerrado.saldo)}"
            return texto + "."
        self._servicio.cambiar_estado(planta.id, nuevo, motivo, fecha, horometro)
        return ""

    @staticmethod
    def _seccion_comercial(destino: EstadoPlanta) -> str:
        return {EstadoPlanta.ALQUILADA: "contrato", EstadoPlanta.VENDIDA: "venta"}.get(destino, "")

    def _liquidador(self, planta_id: int) -> Callable[[date], VistaLiquidacion]:
        """Función que el diálogo llama al cambiar la fecha, para recalcular la liquidación."""
        comercial = self._comercial
        if comercial is None:  # Solo se usa cuando hay servicio comercial
            raise RuntimeError("No se configuró el servicio comercial.")

        def liquidar(fecha: date) -> VistaLiquidacion:
            preliminar = comercial.liquidacion_preliminar(planta_id, fecha)
            if preliminar is None:
                return VistaLiquidacion("Sin contrato activo.", 0, 0)
            alquiler, liquidacion = preliminar
            return VistaLiquidacion(
                f"{alquiler.cliente_nombre} · desde {alquiler.fecha_inicio:%d/%m/%Y}<br>"
                f"{texto_liquidacion(alquiler.modalidad, alquiler.tarifa, liquidacion)}",
                liquidacion.valor,
                alquiler.cobrado,
            )

        return liquidar

    @staticmethod
    def _aviso_transicion(
        planta: Planta,
        destino: EstadoPlanta,
        comercial: bool = False,
        tiene_contrato: bool = False,
    ) -> str:
        """Explica al usuario las consecuencias del cambio antes de confirmarlo."""
        avisos: list[str] = []
        if comercial and planta.estado is EstadoPlanta.ALQUILADA and not tiene_contrato:
            avisos.append(
                "Este alquiler se registró antes de la versión 0.7.0: no tiene contrato "
                "ni liquidación. Si hubo un cobro, regístrelo en la ficha como otro ingreso."
            )
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
            texto += f"\nRecibió el número {formatear_consecutivo(despues.numero_consecutivo)}."
        if despues.horometro_actual != antes.horometro_actual:
            usadas = despues.horometro_actual - antes.horometro_actual
            texto += (
                f"\nLectura del horómetro: {formatear_entero(despues.horometro_actual, 'h')}"
                f" (+{formatear_entero(usadas, 'h')} desde la lectura anterior)."
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

    def _actualizar_alertas(self) -> None:
        if self._mantenimientos is None:
            return
        self._vista.mostrar_alertas(
            [
                (_texto_alerta(a), a.planta.id, _COLOR_ALERTA[a.nivel])
                for a in self._mantenimientos.alertas()
            ]
        )

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
            "ficha": self.ver_ficha,
            "pdf": self.generar_hoja_vida,
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


def _texto_alerta(alerta: AlertaMantenimiento) -> str:
    """Ej. "PE-004 · Vencido: hace 3 días" o "PE-002 · Próximo: en 20 h"."""
    partes: list[str] = []
    if alerta.dias_restantes is not None:
        dias = alerta.dias_restantes
        if dias < 0:
            partes.append(f"hace {-dias} día(s)")
        elif dias == 0:
            partes.append("hoy")
        else:
            partes.append(f"en {dias} día(s)")
    if alerta.horas_restantes is not None:
        horas = alerta.horas_restantes
        partes.append(
            f"{formatear_entero(-horas, 'h')} pasado"
            if horas < 0
            else f"en {formatear_entero(horas, 'h')}"
        )
    numero = formatear_consecutivo(alerta.planta.numero_consecutivo)
    return f"{numero} · {alerta.nivel.etiqueta}: {' / '.join(partes)}"
