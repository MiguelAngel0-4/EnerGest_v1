"""
Pruebas unitarias de las reglas de gastos (Actividad 4.1).

Ruta: tests/unit/test_gasto_service.py
"""

from datetime import date

import pytest

from src.business.exceptions import NegocioError, ValidacionError
from src.business.models.estado_planta import EstadoPlanta as E
from src.business.models.gasto import DatosFactura, DatosGasto
from src.business.models.planta import DatosPlanta
from src.business.services.consecutivo_service import ConsecutivoService
from src.business.services.gasto_service import GastoService
from src.business.services.planta_service import PlantaService
from tests.unit.fakes import AlmacenFake, FakeUnidadDeTrabajo

HOY = date(2026, 10, 9)
FILTROS, REPUESTOS, MANO_DE_OBRA = 1, 2, 4


@pytest.fixture
def servicios() -> tuple[PlantaService, GastoService]:
    almacen = AlmacenFake()
    fabrica = lambda: FakeUnidadDeTrabajo(almacen)  # noqa: E731
    return (
        PlantaService(fabrica, ConsecutivoService(), lambda: HOY),
        GastoService(fabrica, lambda: HOY),
    )


def _gasto(valor: int, categoria: int = FILTROS, factura_id: int | None = None) -> DatosGasto:
    return DatosGasto(categoria, HOY, "Filtro de aceite LF3000", valor, factura_id=factura_id)


def _planta(plantas: PlantaService) -> int:
    return plantas.registrar(DatosPlanta(marca="Cummins", potencia_kva=50)).id


def _factura(gastos: GastoService, valor: int, numero: str = "FE-001") -> int:
    proveedor = gastos.registrar_proveedor("Filtros del Valle", "900.111.222-3")
    return gastos.registrar_factura(DatosFactura(proveedor.id, numero, HOY, valor)).id


# --- Regla 1 y 2: gasto por planta, con o sin factura ------------------------


def test_gasto_sin_factura_queda_sin_soporte(servicios) -> None:
    plantas, gastos = servicios
    planta_id = _planta(plantas)
    gastos.registrar_gasto(planta_id, _gasto(80_000, MANO_DE_OBRA))

    detalle = gastos.listar_gastos(planta_id)[0]
    assert not detalle.tiene_soporte
    assert gastos.resumen(planta_id).sin_soporte == 80_000


# --- Regla 3: factura repartida sin superar su total ------------------------


def test_factura_repartida_entre_dos_plantas(servicios) -> None:
    plantas, gastos = servicios
    p1, p2 = _planta(plantas), _planta(plantas)
    factura_id = _factura(gastos, 300_000)

    gastos.registrar_gasto(p1, _gasto(120_000, factura_id=factura_id))
    gastos.registrar_gasto(p2, _gasto(100_000, factura_id=factura_id))

    factura = gastos.facturas_con_saldo()[0]
    assert (factura.valor_asignado, factura.saldo_por_asignar) == (220_000, 80_000)


def test_no_se_puede_superar_el_saldo_de_la_factura(servicios) -> None:
    plantas, gastos = servicios
    planta_id = _planta(plantas)
    factura_id = _factura(gastos, 100_000)
    gastos.registrar_gasto(planta_id, _gasto(70_000, factura_id=factura_id))

    with pytest.raises(ValidacionError, match=r"saldo por asignar.*30\.000"):
        gastos.registrar_gasto(planta_id, _gasto(30_001, factura_id=factura_id))


def test_factura_agotada_no_aparece_para_asignar(servicios) -> None:
    plantas, gastos = servicios
    factura_id = _factura(gastos, 50_000)
    gastos.registrar_gasto(_planta(plantas), _gasto(50_000, factura_id=factura_id))
    assert gastos.facturas_con_saldo() == []


def test_anular_un_gasto_devuelve_su_valor_al_saldo(servicios) -> None:
    plantas, gastos = servicios
    factura_id = _factura(gastos, 50_000)
    gasto = gastos.registrar_gasto(_planta(plantas), _gasto(50_000, factura_id=factura_id))

    gastos.anular_gasto(gasto.id, "Se asignó a la planta equivocada")

    assert gastos.facturas_con_saldo()[0].saldo_por_asignar == 50_000


# --- Regla 4: factura única por proveedor -----------------------------------


def test_factura_repetida_para_el_mismo_proveedor(servicios) -> None:
    _, gastos = servicios
    proveedor = gastos.registrar_proveedor("Filtros del Valle")
    gastos.registrar_factura(DatosFactura(proveedor.id, "FE-001", HOY, 100_000))
    with pytest.raises(ValidacionError) as error:
        gastos.registrar_factura(DatosFactura(proveedor.id, " fe-001 ", HOY, 50_000))
    assert "numero_factura" in error.value.errores


def test_proveedor_repetido_por_nombre_o_nit(servicios) -> None:
    _, gastos = servicios
    gastos.registrar_proveedor("Filtros del Valle", "900.111.222-3")
    with pytest.raises(ValidacionError) as error:
        gastos.registrar_proveedor("  filtros del valle ", "900.111.222-3")
    assert set(error.value.errores) == {"nombre", "nit"}


# --- Regla 5: plantas vendidas o dadas de baja ------------------------------


def test_no_se_registran_gastos_a_plantas_vendidas(servicios) -> None:
    plantas, gastos = servicios
    planta_id = _planta(plantas)
    plantas.cambiar_estado(planta_id, E.VENDIDA, motivo="Venta")
    with pytest.raises(ValidacionError, match="Vendida"):
        gastos.registrar_gasto(planta_id, _gasto(10_000))


def test_plantas_retiradas_si_admiten_gastos(servicios) -> None:
    plantas, gastos = servicios
    planta_id = _planta(plantas)
    plantas.cambiar_estado(planta_id, E.RETIRADA, motivo="Reparación en bodega")
    assert gastos.registrar_gasto(planta_id, _gasto(10_000)).planta_id == planta_id


# --- Regla 6: validaciones de datos -----------------------------------------


def test_reporta_todos_los_errores_del_gasto(servicios) -> None:
    plantas, gastos = servicios
    datos = DatosGasto(FILTROS, date(2026, 10, 10), "   ", 0, cantidad=0)
    with pytest.raises(ValidacionError) as error:
        gastos.registrar_gasto(_planta(plantas), datos)
    assert set(error.value.errores) == {"fecha", "descripcion", "valor_total", "cantidad"}


# --- Regla 7: anular en lugar de borrar -------------------------------------


def test_anular_exige_motivo_y_no_se_repite(servicios) -> None:
    plantas, gastos = servicios
    gasto = gastos.registrar_gasto(_planta(plantas), _gasto(10_000))

    with pytest.raises(ValidacionError):
        gastos.anular_gasto(gasto.id, "   ")
    gastos.anular_gasto(gasto.id, "Valor mal digitado")
    with pytest.raises(NegocioError, match="ya estaba anulado"):
        gastos.anular_gasto(gasto.id, "Otra vez")


def test_anulados_se_ocultan_pero_no_se_pierden(servicios) -> None:
    plantas, gastos = servicios
    planta_id = _planta(plantas)
    gasto = gastos.registrar_gasto(planta_id, _gasto(10_000))
    gastos.registrar_gasto(planta_id, _gasto(25_000))
    gastos.anular_gasto(gasto.id, "Duplicado")

    assert len(gastos.listar_gastos(planta_id)) == 1
    assert len(gastos.listar_gastos(planta_id, incluir_anulados=True)) == 2
    assert gastos.resumen(planta_id).total == 25_000


# --- Resumen ----------------------------------------------------------------


def test_resumen_por_categoria_de_mayor_a_menor(servicios) -> None:
    plantas, gastos = servicios
    planta_id = _planta(plantas)
    gastos.registrar_gasto(planta_id, _gasto(45_000, FILTROS))
    gastos.registrar_gasto(planta_id, _gasto(300_000, REPUESTOS))
    gastos.registrar_gasto(planta_id, _gasto(15_000, FILTROS))

    resumen = gastos.resumen(planta_id)
    assert resumen.total == 360_000
    assert resumen.por_categoria == (("Repuestos", 300_000), ("Filtros", 60_000))
