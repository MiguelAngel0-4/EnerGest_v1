"""
Pruebas del archivo de datos de la empresa (data/empresa.json).

Ruta: tests/integration/test_empresa_json.py
"""

import json
import logging
from pathlib import Path

import pytest

from src.infrastructure.repositories.empresa_json_repository import (
    NOMBRE_POR_DEFECTO,
    EmpresaJsonRepository,
)
from src.shared.paths import get_resource_path

PLANTILLA = get_resource_path("resources/templates/empresa.json")


def test_primera_vez_crea_el_archivo_con_los_datos_de_la_plantilla(tmp_path: Path) -> None:
    ruta = tmp_path / "data" / "empresa.json"
    empresa = EmpresaJsonRepository(ruta, PLANTILLA).obtener()

    assert ruta.exists()
    assert empresa.nombre == "WG ENERGIA INTEGRAL SAS"
    assert empresa.nit == "901.762.018-1"
    assert empresa.ruta_logo == tmp_path / "data" / "logo_empresa.png"


def test_lee_los_cambios_sin_reiniciar(tmp_path: Path) -> None:
    ruta = tmp_path / "empresa.json"
    repositorio = EmpresaJsonRepository(ruta, PLANTILLA)
    repositorio.obtener()

    datos = json.loads(ruta.read_text(encoding="utf-8"))
    datos["telefono"] = "602 555 0000"
    ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")

    assert repositorio.obtener().telefono == "602 555 0000"


def test_archivo_danado_no_impide_trabajar(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    ruta = tmp_path / "empresa.json"
    ruta.write_text('{"nombre": "WG" "nit": }', encoding="utf-8")  # Falta una coma

    with caplog.at_level(logging.WARNING):
        empresa = EmpresaJsonRepository(ruta, PLANTILLA).obtener()

    assert empresa.nombre == NOMBRE_POR_DEFECTO
    assert "No se pudo leer" in caplog.text
    assert ruta.read_text(encoding="utf-8") == '{"nombre": "WG" "nit": }'  # No lo sobrescribe


def test_sin_plantilla_crea_un_archivo_generico(tmp_path: Path) -> None:
    ruta = tmp_path / "empresa.json"
    empresa = EmpresaJsonRepository(ruta, tmp_path / "no_existe.json").obtener()
    assert empresa.nombre == NOMBRE_POR_DEFECTO and ruta.exists()


def test_campos_vacios_quedan_como_none(tmp_path: Path) -> None:
    ruta = tmp_path / "empresa.json"
    ruta.write_text('{"nombre": "WG", "nit": "  ", "logo": ""}', encoding="utf-8")
    empresa = EmpresaJsonRepository(ruta).obtener()
    assert (empresa.nit, empresa.ruta_logo) == (None, None)
