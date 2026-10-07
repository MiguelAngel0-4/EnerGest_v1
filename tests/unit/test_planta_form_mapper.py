"""
Pruebas del traductor formulario <-> DatosPlanta.

Ruta: tests/unit/test_planta_form_mapper.py
"""

from datetime import date

from src.business.models.planta import DatosPlanta, TipoAceite, TipoCombustible
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
        filtro_aceite="LF3000",
        filtro_combustible="FS1280",
        filtro_agua="WF2071",
        filtro_aire="P181052",
        cantidad_aceite_gal=2.5,
        tipo_aceite=TipoAceite.SAE_25W60,
    )
    assert valores_a_datos(datos_a_valores(datos)) == datos


def test_combustible_viaja_como_texto_en_el_formulario() -> None:
    valores = datos_a_valores(
        DatosPlanta(marca="X", potencia_kva=10, tipo_combustible=TipoCombustible.GAS)
    )
    assert valores["tipo_combustible"] == "GAS"


def test_tipo_de_aceite_viaja_como_texto_en_el_formulario() -> None:
    valores = datos_a_valores(
        DatosPlanta(marca="X", potencia_kva=10, tipo_aceite=TipoAceite.SAE_15W40)
    )
    assert valores["tipo_aceite"] == "SAE_15W40"
    assert valores_a_datos(valores).tipo_aceite is TipoAceite.SAE_15W40


def test_formulario_vacio_produce_datos_que_el_servicio_rechazara() -> None:
    datos = valores_a_datos({})
    assert datos.marca == "" and datos.potencia_kva == 0 and datos.tipo_combustible is None
