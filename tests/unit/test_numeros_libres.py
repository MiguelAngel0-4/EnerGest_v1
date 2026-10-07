"""
Pruebas de las consultas de números libres (panel informativo del inventario).

Ruta: tests/unit/test_numeros_libres.py
"""

from datetime import date

import pytest

from src.business.models.estado_planta import EstadoPlanta as E
from src.business.models.planta import DatosPlanta
from src.business.services.consecutivo_service import ConsecutivoService
from src.business.services.planta_service import PlantaService
from tests.unit.fakes import AlmacenFake, FakeUnidadDeTrabajo


@pytest.mark.parametrize(
    ("en_uso", "esperado"),
    [
        (set(), []),
        ({1, 2, 3}, []),
        ({2}, [1]),
        ({1, 2, 4, 5, 7}, [3, 6]),
    ],
)
def test_calcular_libres(en_uso: set[int], esperado: list[int]) -> None:
    assert ConsecutivoService.calcular_libres(en_uso) == esperado


def test_servicio_informa_libres_y_proximo_numero() -> None:
    almacen = AlmacenFake()
    servicio = PlantaService(
        lambda: FakeUnidadDeTrabajo(almacen), ConsecutivoService(), hoy=lambda: date(2026, 9, 30)
    )
    plantas = [servicio.registrar(DatosPlanta(marca="Cummins", potencia_kva=50)) for _ in range(5)]
    servicio.cambiar_estado(plantas[1].id, E.VENDIDA, motivo="Venta")  # libera 2
    servicio.cambiar_estado(plantas[3].id, E.DADA_DE_BAJA, motivo="Daño")  # libera 4

    assert servicio.numeros_libres() == [2, 4]
    assert servicio.proximo_numero() == 2
