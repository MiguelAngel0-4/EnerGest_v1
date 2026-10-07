"""
Pruebas unitarias del validador de datos de planta.

Ruta: tests/unit/test_planta_validator.py
"""

from dataclasses import replace
from datetime import date

from src.business.models.planta import DatosPlanta
from src.business.validators.planta_validator import normalizar_datos, validar_datos

HOY = date(2026, 9, 30)
VALIDOS = DatosPlanta(marca="Cummins", potencia_kva=100, potencia_kw=80, fases=3)


def test_datos_validos_no_generan_errores() -> None:
    assert validar_datos(VALIDOS, HOY) == {}


def test_normalizar_limpia_espacios_y_convierte_vacios_en_none() -> None:
    datos = replace(VALIDOS, marca="  Cummins ", numero_serie="   ", modelo=" C100 ")
    limpio = normalizar_datos(datos)
    assert limpio.marca == "Cummins"
    assert limpio.numero_serie is None
    assert limpio.modelo == "C100"


def test_marca_vacia() -> None:
    errores = validar_datos(normalizar_datos(replace(VALIDOS, marca="   ")), HOY)
    assert "marca" in errores


def test_kw_no_puede_superar_kva() -> None:
    errores = validar_datos(replace(VALIDOS, potencia_kva=50, potencia_kw=60), HOY)
    assert "potencia_kw" in errores


def test_fases_invalidas() -> None:
    assert "fases" in validar_datos(replace(VALIDOS, fases=2), HOY)


def test_fecha_adquisicion_futura() -> None:
    errores = validar_datos(replace(VALIDOS, fecha_adquisicion=date(2026, 10, 1)), HOY)
    assert "fecha_adquisicion" in errores


def test_reporta_todos_los_errores_a_la_vez() -> None:
    datos = DatosPlanta(
        marca="", potencia_kva=0, fases=2, valor_compra=-1, horometro_inicial=-5
    )
    errores = validar_datos(datos, HOY)
    assert set(errores) == {"marca", "potencia_kva", "fases", "valor_compra", "horometro_inicial"}
