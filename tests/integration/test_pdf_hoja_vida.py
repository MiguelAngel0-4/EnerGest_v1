"""
Pruebas del PDF real de la hoja de vida (ReportLab + lectura con pypdf).

Ruta: tests/integration/test_pdf_hoja_vida.py
"""

from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

import pytest

from src.business.exceptions import DocumentoError
from src.business.models.estado_planta import EstadoPlanta as E
from src.business.models.hoja_vida import DatosEmpresa, HojaDeVida
from src.business.models.planta import (
    CambioEstado,
    DatosPlanta,
    Planta,
    RegistroConsecutivo,
    TipoAceite,
)
from src.infrastructure.reports.pdf_hoja_vida import GeneradorPdfHojaVida

pypdf = pytest.importorskip("pypdf", reason="Instale pypdf: pip install pypdf")

DATOS = DatosPlanta(
    marca="Cummins",
    potencia_kva=150,
    modelo="C150D6",
    numero_serie="CUM-15088",
    filtro_aceite="Fleetguard LF3000",
    cantidad_aceite_gal=4.0,
    tipo_aceite=TipoAceite.SAE_15W40,
)
PLANTA = Planta(1, 1, E.DISPONIBLE, DATOS, datetime(2026, 1, 10, 9, 0), 1200)
EMPRESA = DatosEmpresa("Plantas del Valle S.A.S.", nit="900.123.456-7")


def _hoja(planta: Planta = PLANTA, cambios: int = 1, empresa: DatosEmpresa = EMPRESA) -> HojaDeVida:
    historial = [CambioEstado(planta.id, None, E.DISPONIBLE, date(2026, 1, 10), "Registro inicial")]
    for i in range(cambios - 1):  # Alterna alquileres y regresos con lecturas crecientes
        anterior, nuevo = (E.DISPONIBLE, E.ALQUILADA) if i % 2 == 0 else (E.ALQUILADA, E.DISPONIBLE)
        historial.append(CambioEstado(planta.id, anterior, nuevo, date(2026, 2, 1), None, 1200 + i))
    return HojaDeVida(
        planta=planta,
        cambios_estado=tuple(historial),
        consecutivos=(RegistroConsecutivo(planta.id, 1, date(2026, 1, 10)),),
        empresa=empresa,
        generado_en=datetime(2026, 10, 7, 14, 30),
        version_app="0.4.0",
    )


def _texto(ruta: Path) -> list[str]:
    """Texto de cada página del PDF."""
    return [pagina.extract_text() for pagina in pypdf.PdfReader(ruta).pages]


def test_contiene_los_datos_principales(tmp_path: Path) -> None:
    ruta = GeneradorPdfHojaVida().generar(_hoja(), tmp_path / "hv.pdf")
    texto = " ".join(_texto(ruta))

    for esperado in [
        "HOJA DE VIDA",
        "PE-001",
        "Plantas del Valle S.A.S.",
        "Fleetguard LF3000",
        "15W-40",
        "1.200 h",
        "No registrado",  # Los filtros de agua y aire no tienen datos
        "Página 1 de 1",
        "EnerGest v0.4.0",
    ]:
        assert esperado in texto, f"Falta '{esperado}' en el PDF"


def test_planta_vendida_muestra_numero_liberado(tmp_path: Path) -> None:
    vendida = replace(PLANTA, estado=E.VENDIDA, numero_consecutivo=None)
    texto = " ".join(_texto(GeneradorPdfHojaVida().generar(_hoja(vendida), tmp_path / "v.pdf")))
    assert "PE-001" in texto and "Número liberado" in texto


def test_historial_largo_ocupa_varias_paginas_con_encabezados(tmp_path: Path) -> None:
    paginas = _texto(GeneradorPdfHojaVida().generar(_hoja(cambios=80), tmp_path / "largo.pdf"))

    assert len(paginas) >= 2
    assert f"Página 2 de {len(paginas)}" in paginas[1]
    assert "Hoja de vida técnica – PE-001" in paginas[1]  # Encabezado corto
    assert "Estado anterior" in paginas[1]  # El encabezado de la tabla se repite


def test_caracteres_especiales_no_rompen_el_pdf(tmp_path: Path) -> None:
    datos = replace(DATOS, marca="A&B <Diésel> Ñandú", observaciones="50% & más")
    rara = replace(PLANTA, datos=datos)
    texto = " ".join(_texto(GeneradorPdfHojaVida().generar(_hoja(rara), tmp_path / "raro.pdf")))
    assert "A&B <Diésel> Ñandú" in texto and "50% & más" in texto


def test_logo_valido_y_logo_danado(tmp_path: Path) -> None:
    from PIL import Image as ImagenPil

    logo = tmp_path / "logo.png"
    ImagenPil.new("RGB", (300, 120), "navy").save(logo)
    danado = tmp_path / "danado.png"
    danado.write_text("esto no es una imagen")

    con_logo = GeneradorPdfHojaVida().generar(
        _hoja(empresa=replace(EMPRESA, ruta_logo=logo)), tmp_path / "logo.pdf"
    )
    sin_logo = GeneradorPdfHojaVida().generar(
        _hoja(empresa=replace(EMPRESA, ruta_logo=danado)), tmp_path / "danado.pdf"
    )

    recursos = pypdf.PdfReader(con_logo).pages[0]["/Resources"]
    assert "/XObject" in recursos  # La imagen quedó incrustada
    assert "PE-001" in _texto(sin_logo)[0]  # Un logo dañado no impide generar el PDF


def test_destino_ocupado_da_error_claro_y_no_deja_basura(tmp_path: Path) -> None:
    ocupado = tmp_path / "hv.pdf"
    ocupado.mkdir()  # Una carpeta con ese nombre impide escribir el archivo

    with pytest.raises(DocumentoError, match="No se pudo guardar"):
        GeneradorPdfHojaVida().generar(_hoja(), ocupado)

    assert [p.name for p in tmp_path.iterdir()] == ["hv.pdf"]  # Sin temporales huérfanos
