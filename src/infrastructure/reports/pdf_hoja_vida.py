"""
Generador PDF de la hoja de vida técnica (implementación con ReportLab).

Ruta: src/infrastructure/reports/pdf_hoja_vida.py

Cumple el contrato IGeneradorHojaVida. Usa "Platypus", el motor de
maquetación de ReportLab: el documento se arma como una lista de bloques
(párrafos, tablas, espacios) y ReportLab los acomoda en páginas, repitiendo
encabezados de tabla y saltando de página cuando hace falta.
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Final
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    Flowable,
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.business.exceptions import DocumentoError
from src.business.models.hoja_vida import HojaDeVida
from src.shared.formatters import (
    formatear_consecutivo,
    formatear_decimal,
    formatear_entero,
    formatear_moneda,
)

logger = logging.getLogger(__name__)

# --- Apariencia (colores de EnerGest) -----------------------------------------
AZUL: Final = colors.HexColor("#1F3A5F")
AZUL_CLARO: Final = colors.HexColor("#E9EEF4")
CELESTE: Final = colors.HexColor("#F3F8FD")
GRIS: Final = colors.HexColor("#8A939B")
BORDE: Final = colors.HexColor("#C4CDD5")

MARGEN: Final[float] = 1.8 * cm
ANCHO_UTIL: Final[float] = letter[0] - 2 * MARGEN  # Ancho de la hoja carta sin márgenes
NO_REGISTRADO: Final[str] = "No registrado"
FORMATO_FECHA: Final[str] = "%d/%m/%Y"
FASES: Final[dict[int, str]] = {1: "Monofásica (1)", 3: "Trifásica (3)"}

_NORMAL = ParagraphStyle("normal", fontName="Helvetica", fontSize=9, leading=11.5)
_VACIO = ParagraphStyle("vacio", parent=_NORMAL, fontName="Helvetica-Oblique", textColor=GRIS)
_ETIQUETA = ParagraphStyle(
    "etiqueta", parent=_NORMAL, fontName="Helvetica-Bold", fontSize=8, textColor=AZUL
)
_ENCABEZADO_TABLA = ParagraphStyle(
    "encabezado_tabla", parent=_ETIQUETA, textColor=colors.white
)
_SECCION = ParagraphStyle(
    "seccion", parent=_NORMAL, fontName="Helvetica-Bold", fontSize=10, textColor=colors.white
)
_TITULO = ParagraphStyle(
    "titulo",
    parent=_NORMAL,
    fontName="Helvetica-Bold",
    fontSize=14,
    leading=18,
    textColor=AZUL,
    alignment=TA_CENTER,
)
_SUBTITULO = ParagraphStyle(
    "subtitulo", parent=_NORMAL, fontSize=10, textColor=GRIS, alignment=TA_CENTER
)
_EMPRESA = ParagraphStyle("empresa", parent=_NORMAL, fontName="Helvetica-Bold", fontSize=12)
_NUMERO = ParagraphStyle(
    "numero",
    parent=_NORMAL,
    fontName="Helvetica-Bold",
    fontSize=18,
    leading=22,
    textColor=AZUL,
    alignment=TA_CENTER,
)
_NUMERO_LIBERADO = ParagraphStyle("numero_liberado", parent=_NUMERO, textColor=GRIS)
_NUMERO_PIE = ParagraphStyle("numero_pie", parent=_NORMAL, fontSize=7, alignment=TA_CENTER)


class GeneradorPdfHojaVida:
    """Produce la hoja de vida técnica en PDF, tamaño carta."""

    def generar(self, hoja: HojaDeVida, destino: Path) -> Path:
        """
        Escribe el PDF de forma segura: primero en un archivo temporal de la misma
        carpeta y, solo si todo salió bien, lo renombra al nombre definitivo.
        Así nunca queda un PDF a medio escribir con el nombre final.

        Raises:
            DocumentoError: Si no se pudo escribir (archivo abierto, sin permisos...).
        """
        temporal: Path | None = None
        try:
            destino.parent.mkdir(parents=True, exist_ok=True)
            descriptor, nombre_temporal = tempfile.mkstemp(suffix=".pdf", dir=destino.parent)
            os.close(descriptor)
            temporal = Path(nombre_temporal)
            self._construir(hoja, temporal)
            os.replace(temporal, destino)  # Reemplazo atómico
            return destino
        except OSError as exc:
            logger.exception("No se pudo escribir la hoja de vida en %s", destino)
            raise DocumentoError(
                f"No se pudo guardar el PDF en:\n{destino}\n\n"
                "Si el archivo está abierto en otro programa, ciérrelo e intente de nuevo."
            ) from exc
        except Exception as exc:
            logger.exception("Error inesperado al construir la hoja de vida.")
            raise DocumentoError(
                "Ocurrió un error inesperado al crear el PDF. "
                "Los detalles quedaron registrados en el log."
            ) from exc
        finally:
            if temporal is not None and temporal.exists():
                temporal.unlink(missing_ok=True)

    # ------------------------------------------------------------------ #
    # Construcción del documento
    # ------------------------------------------------------------------ #

    def _construir(self, hoja: HojaDeVida, ruta: Path) -> None:
        datos = hoja.planta.datos
        numero = formatear_consecutivo(hoja.ultimo_numero)
        nombre_equipo = " ".join(filter(None, [datos.marca, datos.modelo]))

        documento = SimpleDocTemplate(
            str(ruta),
            pagesize=letter,
            leftMargin=MARGEN,
            rightMargin=MARGEN,
            topMargin=1.5 * cm,
            bottomMargin=2.0 * cm,
            title=f"Hoja de vida {numero} – {nombre_equipo}",
            author=hoja.empresa.nombre,
            subject="Hoja de vida técnica de planta eléctrica",
            creator=f"EnerGest v{hoja.version_app}",
        )
        pie = (
            f"Generado por EnerGest v{hoja.version_app} · "
            f"{hoja.generado_en:%d/%m/%Y %H:%M} · Documento de uso interno"
        )
        encabezado_corto = f"Hoja de vida técnica – {numero} · {nombre_equipo}"

        def fabricar_canvas(*args: Any, **kwargs: Any) -> Canvas:
            return _CanvasNumerado(*args, pie=pie, encabezado=encabezado_corto, **kwargs)

        bloques: list[Flowable] = [
            *self._encabezado(hoja),
            *self._seccion("1. Identificación", self._tabla_datos(self._identificacion(hoja))),
            *self._seccion(
                "2. Especificaciones técnicas", self._tabla_datos(self._especificaciones(hoja))
            ),
            *self._seccion(
                "3. Mantenimiento: filtros y aceite",
                self._tabla_datos(self._mantenimiento(hoja), fondo_valores=CELESTE),
            ),
            *self._seccion("4. Operación", self._tabla_operacion(hoja)),
            *self._seccion("5. Historial de estados", self._tabla_estados(hoja)),
            *self._seccion("6. Historial de números consecutivos", self._tabla_consecutivos(hoja)),
            Spacer(1, 0.7 * cm),
            KeepTogether(self._firmas()),  # Las firmas nunca se parten entre páginas
        ]
        documento.build(bloques, canvasmaker=fabricar_canvas)

    # --- Encabezado ------------------------------------------------------------

    def _encabezado(self, hoja: HojaDeVida) -> list[Flowable]:
        empresa = hoja.empresa
        lineas_empresa = [f"<b>{escape(empresa.nombre)}</b>"]
        detalle = " · ".join(
            filter(
                None,
                [
                    f"NIT {escape(empresa.nit)}" if empresa.nit else None,
                    f"Tel. {escape(empresa.telefono)}" if empresa.telefono else None,
                ],
            )
        )
        if detalle:
            lineas_empresa.append(detalle)
        if empresa.direccion:
            lineas_empresa.append(escape(empresa.direccion))

        # Un número liberado se muestra en gris: otra planta podría tenerlo hoy.
        vigente = hoja.planta.numero_consecutivo is not None
        caja_numero = Table(
            [
                [
                    Paragraph(
                        escape(formatear_consecutivo(hoja.ultimo_numero)),
                        _NUMERO if vigente else _NUMERO_LIBERADO,
                    )
                ],
                [Paragraph(self._texto_numero(hoja), _NUMERO_PIE)],
            ],
            colWidths=[4 * cm],
            style=TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 1.2, AZUL),
                    ("BACKGROUND", (0, 0), (-1, -1), AZUL_CLARO),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                ]
            ),
        )
        texto_empresa = Paragraph("<br/>".join(lineas_empresa), _NORMAL)
        logo = self._logo(hoja)
        if logo is None:  # Sin logo: la empresa ocupa ese espacio (sin hueco a la izquierda)
            fila, anchos = [texto_empresa, caja_numero], [ANCHO_UTIL - 4.2 * cm, 4.2 * cm]
        else:
            fila = [logo, texto_empresa, caja_numero]
            anchos = [3.4 * cm, ANCHO_UTIL - 7.6 * cm, 4.2 * cm]
        encabezado = Table(
            [fila],
            colWidths=anchos,
            style=TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LINEBELOW", (0, 0), (-1, -1), 1.5, AZUL),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            ),
        )
        datos = hoja.planta.datos
        serial = f"Serial {datos.numero_serie}" if datos.numero_serie else None
        subtitulo = " · ".join(filter(None, [datos.marca, datos.modelo, serial]))
        return [
            encabezado,
            Spacer(1, 0.25 * cm),
            Paragraph("HOJA DE VIDA TÉCNICA – PLANTA ELÉCTRICA", _TITULO),
            Paragraph(escape(subtitulo), _SUBTITULO),
            Spacer(1, 0.2 * cm),
        ]

    @staticmethod
    def _texto_numero(hoja: HojaDeVida) -> str:
        """Debajo del número: "N° consecutivo" o, si ya no lo tiene, por qué."""
        if hoja.planta.numero_consecutivo is not None:
            return "N° consecutivo"
        if hoja.ultimo_numero is None:
            return "Sin número"
        return f"Número liberado · {escape(hoja.planta.estado.etiqueta)}"

    @staticmethod
    def _logo(hoja: HojaDeVida) -> Flowable | None:
        """Logo de la empresa, escalado sin deformarlo. Si falta o está dañado, se omite."""
        ruta = hoja.empresa.ruta_logo
        if ruta is None or not ruta.is_file():
            return None
        try:
            ancho_original, alto_original = ImageReader(str(ruta)).getSize()
            escala = min(3.0 * cm / ancho_original, 2.0 * cm / alto_original)
            return Image(str(ruta), ancho_original * escala, alto_original * escala)
        except Exception:
            logger.warning("No se pudo cargar el logo %s; se omite del PDF.", ruta)
            return None

    # --- Contenido de las secciones (pares etiqueta / valor) -------------------

    @staticmethod
    def _identificacion(hoja: HojaDeVida) -> list[tuple[str, str | None]]:
        planta, datos = hoja.planta, hoja.planta.datos
        return [
            ("Marca", datos.marca),
            ("Modelo", datos.modelo),
            ("Serial", datos.numero_serie),
            ("Estado actual", planta.estado.etiqueta),
            ("Fecha de adquisición", _fecha(datos.fecha_adquisicion)),
            ("Fecha de registro", planta.fecha_registro.strftime(FORMATO_FECHA)),
            ("Valor de compra", _moneda(datos.valor_compra)),
        ]

    @staticmethod
    def _especificaciones(hoja: HojaDeVida) -> list[tuple[str, str | None]]:
        datos = hoja.planta.datos
        return [
            ("Potencia aparente", formatear_decimal(datos.potencia_kva, "kVA")),
            ("Potencia activa", _decimal(datos.potencia_kw, "kW")),
            ("Voltaje", datos.voltaje),
            ("Fases", FASES.get(datos.fases) if datos.fases else None),
            ("Combustible", datos.tipo_combustible.etiqueta if datos.tipo_combustible else None),
            ("Capacidad del tanque", _decimal(datos.capacidad_tanque_gal, "gal")),
        ]

    @staticmethod
    def _mantenimiento(hoja: HojaDeVida) -> list[tuple[str, str | None]]:
        datos = hoja.planta.datos
        return [
            ("Filtro de aceite", datos.filtro_aceite),
            ("Filtro de combustible / separador", datos.filtro_combustible),
            ("Filtro de agua", datos.filtro_agua),
            ("Filtro de aire", datos.filtro_aire),
            ("Cantidad de aceite", _decimal(datos.cantidad_aceite_gal, "gal")),
            ("Tipo de aceite", datos.tipo_aceite.etiqueta if datos.tipo_aceite else None),
        ]

    # --- Tablas ------------------------------------------------------------------

    @staticmethod
    def _seccion(titulo: str, contenido: Flowable) -> list[Flowable]:
        """Franja azul con el título + contenido. KeepTogether evita títulos huérfanos."""
        franja = Table(
            [[Paragraph(titulo.upper(), _SECCION)]],
            colWidths=[ANCHO_UTIL],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), AZUL),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            ),
        )
        return [Spacer(1, 0.25 * cm), KeepTogether([franja, Spacer(1, 0.08 * cm), contenido])]

    @staticmethod
    def _tabla_datos(
        pares: list[tuple[str, str | None]], fondo_valores: Any = None
    ) -> Table:
        """Cuadrícula de 2 pares por fila: Etiqueta | Valor | Etiqueta | Valor."""
        celdas = [(Paragraph(etiqueta, _ETIQUETA), _valor(valor)) for etiqueta, valor in pares]
        if len(celdas) % 2:
            celdas.append(("", ""))
        filas = [[*celdas[i], *celdas[i + 1]] for i in range(0, len(celdas), 2)]
        ancho_etiqueta = 3.6 * cm
        ancho_valor = ANCHO_UTIL / 2 - ancho_etiqueta
        estilo = [
            ("GRID", (0, 0), (-1, -1), 0.5, BORDE),
            ("BACKGROUND", (0, 0), (0, -1), AZUL_CLARO),
            ("BACKGROUND", (2, 0), (2, -1), AZUL_CLARO),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
        if fondo_valores is not None:
            estilo += [
                ("BACKGROUND", (1, 0), (1, -1), fondo_valores),
                ("BACKGROUND", (3, 0), (3, -1), fondo_valores),
            ]
        return Table(
            filas,
            colWidths=[ancho_etiqueta, ancho_valor, ancho_etiqueta, ancho_valor],
            style=TableStyle(estilo),
        )

    def _tabla_operacion(self, hoja: HojaDeVida) -> Table:
        datos = hoja.planta.datos
        tabla = self._tabla_datos(
            [
                ("Horómetro inicial", formatear_entero(datos.horometro_inicial, "h")),
                ("Última lectura", formatear_entero(hoja.planta.horometro_actual, "h")),
            ]
        )
        fila_observaciones = [Paragraph("Observaciones", _ETIQUETA), _valor(datos.observaciones)]
        observaciones = Table(
            [fila_observaciones],
            colWidths=[3.6 * cm, ANCHO_UTIL - 3.6 * cm],
            style=TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, BORDE),
                    ("BACKGROUND", (0, 0), (0, -1), AZUL_CLARO),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            ),
        )
        sin_relleno = TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
        return Table([[tabla], [observaciones]], colWidths=[ANCHO_UTIL], style=sin_relleno)

    @staticmethod
    def _tabla_estados(hoja: HojaDeVida) -> Table:
        filas = [
            [
                _texto(c.fecha.strftime(FORMATO_FECHA)),
                _texto(c.estado_anterior.etiqueta if c.estado_anterior else "— (registro)"),
                _texto(c.estado_nuevo.etiqueta),
                _texto(formatear_entero(c.horometro, "h") if c.horometro is not None else ""),
                _texto(c.motivo or ""),
            ]
            for c in hoja.cambios_estado
        ]
        return _tabla_historial(
            ["Fecha", "Estado anterior", "Estado nuevo", "Horómetro", "Motivo"],
            filas,
            [2.2 * cm, 3.0 * cm, 3.0 * cm, 2.2 * cm, ANCHO_UTIL - 10.4 * cm],
        )

    @staticmethod
    def _tabla_consecutivos(hoja: HojaDeVida) -> Table:
        filas = [
            [
                _texto(formatear_consecutivo(r.numero)),
                _texto(r.fecha_asignacion.strftime(FORMATO_FECHA)),
                _texto(
                    r.fecha_liberacion.strftime(FORMATO_FECHA) if r.fecha_liberacion else "Vigente"
                ),
                _texto(r.motivo_liberacion or ""),
            ]
            for r in hoja.consecutivos
        ]
        return _tabla_historial(
            ["Número", "Asignado", "Liberado", "Motivo de liberación"],
            filas,
            [2.2 * cm, 2.6 * cm, 2.6 * cm, ANCHO_UTIL - 7.4 * cm],
        )

    @staticmethod
    def _firmas() -> Table:
        linea = "_" * 38
        return Table(
            [
                [Paragraph(linea, _NORMAL), Paragraph(linea, _NORMAL)],
                [Paragraph("Elaborado por", _ETIQUETA), Paragraph("Revisado por", _ETIQUETA)],
                [Paragraph("Fecha:", _NORMAL), Paragraph("Fecha:", _NORMAL)],
            ],
            colWidths=[ANCHO_UTIL / 2, ANCHO_UTIL / 2],
        )


# --- Funciones auxiliares ---------------------------------------------------------


def _valor(texto: str | None) -> Paragraph:
    """
    Celda de valor. Los datos faltantes se muestran como "No registrado" en gris:
    un hueco visible invita a completar la ficha.

    escape() es indispensable: Paragraph interpreta etiquetas tipo HTML, así que
    un dato como "Filtro <A&B>" rompería el PDF si no se escapa.
    """
    if texto is None or not str(texto).strip():
        return Paragraph(NO_REGISTRADO, _VACIO)
    return Paragraph(escape(str(texto)), _NORMAL)


def _texto(texto: str) -> Paragraph:
    return Paragraph(escape(texto), _NORMAL)


def _fecha(valor: Any) -> str | None:
    return valor.strftime(FORMATO_FECHA) if valor is not None else None


def _moneda(valor: int | None) -> str | None:
    return formatear_moneda(valor) if valor else None


def _decimal(valor: float | None, sufijo: str) -> str | None:
    return formatear_decimal(valor, sufijo) if valor is not None else None


def _tabla_historial(
    encabezados: list[str], filas: list[list[Paragraph]], anchos: list[float]
) -> Table:
    """Tabla con encabezado azul que se REPITE en cada página (repeatRows=1)."""
    if not filas:
        filas = [[Paragraph("Sin registros.", _VACIO), *[""] * (len(encabezados) - 1)]]
    datos = [[Paragraph(e, _ENCABEZADO_TABLA) for e in encabezados], *filas]
    return Table(
        datos,
        colWidths=anchos,
        repeatRows=1,
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), AZUL),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CELESTE]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        ),
    )


class _CanvasNumerado(Canvas):
    """
    Lienzo que escribe "Página X de Y" en cada hoja.

    El total de páginas no se conoce hasta terminar el documento, así que cada
    página se guarda en memoria y el pie se dibuja al final, en save().
    """

    def __init__(self, *args: Any, pie: str, encabezado: str, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._pie = pie
        self._encabezado_corto = encabezado
        self._paginas: list[dict[str, Any]] = []

    def showPage(self) -> None:  # Sobrescribe un método de ReportLab (nombre fijo)
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            self._dibujar_marco(total)
            super().showPage()
        super().save()

    def _dibujar_marco(self, total: int) -> None:
        ancho, alto = letter
        self.setStrokeColor(BORDE)
        self.setLineWidth(0.5)
        self.line(MARGEN, 1.5 * cm, ancho - MARGEN, 1.5 * cm)
        self.setFont("Helvetica", 7.5)
        self.setFillColor(GRIS)
        self.drawString(MARGEN, 1.05 * cm, self._pie)
        self.drawRightString(ancho - MARGEN, 1.05 * cm, f"Página {self._pageNumber} de {total}")
        if self._pageNumber > 1:  # Desde la página 2: encabezado corto para identificar la hoja
            self.drawString(MARGEN, alto - 1.1 * cm, self._encabezado_corto)
            self.line(MARGEN, alto - 1.3 * cm, ancho - MARGEN, alto - 1.3 * cm)
