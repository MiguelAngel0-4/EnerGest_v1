"""
Pruebas unitarias del servicio de hojas de vida (sin PDF real).

Ruta: tests/unit/test_hoja_vida_service.py
"""

from datetime import date, datetime
from pathlib import Path

import pytest

from src.business.exceptions import PlantaNoEncontradaError
from src.business.models.estado_planta import EstadoPlanta as E
from src.business.models.hoja_vida import DatosEmpresa, HojaDeVida
from src.business.models.planta import DatosPlanta
from src.business.services.consecutivo_service import ConsecutivoService
from src.business.services.hoja_vida_service import HojaVidaService
from src.business.services.planta_service import PlantaService
from tests.unit.fakes import AlmacenFake, FakeUnidadDeTrabajo

AHORA = datetime(2026, 10, 7, 14, 30)


class GeneradorFalso:
    """Guarda lo que recibe en lugar de crear un PDF."""

    def __init__(self) -> None:
        self.recibidas: list[tuple[HojaDeVida, Path]] = []

    def generar(self, hoja: HojaDeVida, destino: Path) -> Path:
        self.recibidas.append((hoja, destino))
        return destino


@pytest.fixture
def entorno() -> tuple[PlantaService, HojaVidaService, GeneradorFalso, list[DatosEmpresa]]:
    almacen = AlmacenFake()
    fabrica = lambda: FakeUnidadDeTrabajo(almacen)  # noqa: E731
    plantas = PlantaService(fabrica, ConsecutivoService(), lambda: date(2026, 10, 7))
    generador = GeneradorFalso()
    empresa = [DatosEmpresa("Empresa Uno")]  # Lista: permite cambiarla durante la prueba
    hojas = HojaVidaService(fabrica, generador, lambda: empresa[0], "0.4.0", lambda: AHORA)
    return plantas, hojas, generador, empresa


def test_preparar_reune_todo_el_contenido(entorno) -> None:
    plantas, hojas, _, _ = entorno
    planta = plantas.registrar(DatosPlanta(marca="Cummins", potencia_kva=50))
    plantas.cambiar_estado(planta.id, E.ALQUILADA, horometro=10)

    hoja = hojas.preparar(planta.id)

    assert hoja.planta.estado is E.ALQUILADA
    assert [c.estado_nuevo for c in hoja.cambios_estado] == [E.DISPONIBLE, E.ALQUILADA]
    assert [r.numero for r in hoja.consecutivos] == [1]
    assert (hoja.empresa.nombre, hoja.version_app, hoja.generado_en) == (
        "Empresa Uno",
        "0.4.0",
        AHORA,
    )


def test_planta_vendida_conserva_su_ultimo_numero(entorno) -> None:
    plantas, hojas, _, _ = entorno
    planta = plantas.registrar(DatosPlanta(marca="Cummins", potencia_kva=50))
    plantas.cambiar_estado(planta.id, E.VENDIDA, motivo="Venta")

    hoja = hojas.preparar(planta.id)

    assert hoja.planta.numero_consecutivo is None
    assert hoja.ultimo_numero == 1


def test_los_datos_de_la_empresa_se_leen_en_cada_documento(entorno) -> None:
    plantas, hojas, _, empresa = entorno
    planta = plantas.registrar(DatosPlanta(marca="Cummins", potencia_kva=50))
    empresa[0] = DatosEmpresa("Empresa Renombrada")
    assert hojas.preparar(planta.id).empresa.nombre == "Empresa Renombrada"


def test_exportar_entrega_el_contenido_al_generador(entorno, tmp_path: Path) -> None:
    plantas, hojas, generador, _ = entorno
    planta = plantas.registrar(DatosPlanta(marca="Cummins", potencia_kva=50))
    destino = tmp_path / "hv.pdf"

    assert hojas.exportar(planta.id, destino) == destino
    hoja, ruta = generador.recibidas[0]
    assert (hoja.planta.id, ruta) == (planta.id, destino)


def test_planta_inexistente(entorno, tmp_path: Path) -> None:
    _, hojas, generador, _ = entorno
    with pytest.raises(PlantaNoEncontradaError):
        hojas.exportar(999, tmp_path / "x.pdf")
    assert generador.recibidas == []
