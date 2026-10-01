"""
Pruebas del traductor formulario <-> DatosPlanta.

Ruta: tests/unit/test_planta_form_mapper.py
"""

from datetime import date

from src.business.models.planta import DatosPlanta, TipoCombustible
from src.presentation.controllers.planta_form_mapper import datos_a_valores, valores_a_datos


def test_ida_y_vuelta_conserva_todos_los_datos() -> None:
    datos = DatosPlanta(
        marca="Cummins",
        potencia_kva=125.5,
        modelo="C125",
        numero_serie="SN-1",
        potencia_kw=100.0,
        voltaje="220 V",
        fases=3,
        tipo_combustible=TipoCombustible.DIESEL,
        capacidad_tanque_gal=55.0,
        fecha_adquisicion=date(2024, 5, 20),
        valor_compra=85_000_000,
        horometro_inicial=1200,
        observaciones="Cabina insonorizada",
    )
    assert valores_a_datos(datos_a_valores(datos)) == datos


def test_combustible_viaja_como_texto_en_el_formulario() -> None:
    valores = datos_a_valores(
        DatosPlanta(marca="X", potencia_kva=10, tipo_combustible=TipoCombustible.GASOLINA)
    )
    assert valores["tipo_combustible"] == "GASOLINA"


def test_formulario_vacio_produce_datos_que_el_servicio_rechazara() -> None:
    datos = valores_a_datos({})
    assert datos.marca == "" and datos.potencia_kva == 0 and datos.tipo_combustible is None
