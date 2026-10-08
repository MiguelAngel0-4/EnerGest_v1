"""
Pruebas de integración del módulo de gastos sobre SQLite real.

Ruta: tests/integration/test_gastos_sqlite.py

Comprueban que las consultas SQL calculan saldos, totales y detalles igual
que los dobles en memoria, y que el esquema respalda las reglas.
"""

from datetime import date
from pathlib import Path

import pytest

from src.business.exceptions import PersistenciaError, ValidacionError
from src.business.models.estado_planta import EstadoPlanta as E
from src.business.models.gasto import DatosFactura, DatosGasto
from src.business.models.planta import DatosPlanta
from src.business.services.consecutivo_service import ConsecutivoService
from src.business.services.gasto_service import GastoService
from src.business.services.planta_service import PlantaService
from src.config import settings
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.repositories.sqlite_unidad_de_trabajo import (
    SqliteUnidadDeTrabajo,
    crear_fabrica_uow,
)
from src.shared.paths import get_resource_path

HOY = date(2026, 10, 9)


@pytest.fixture
def entorno(tmp_path: Path) -> tuple[DatabaseManager, PlantaService, GastoService]:
    db = DatabaseManager(tmp_path / "gastos.db")
    db.initialize_schema(get_resource_path(settings.SCHEMA_RELATIVE_PATH))
    fabrica = crear_fabrica_uow(db)
    return (
        db,
        PlantaService(fabrica, ConsecutivoService(), lambda: HOY),
        GastoService(fabrica, lambda: HOY),
    )


def _categoria(gastos: GastoService, nombre: str) -> int:
    return next(c.id for c in gastos.listar_categorias() if c.nombre == nombre)


def test_categorias_iniciales_disponibles(entorno) -> None:
    _, _, gastos = entorno
    assert [c.nombre for c in gastos.listar_categorias()] == [
        "Filtros",
        "Repuestos",
        "Aceite y lubricantes",
        "Mano de obra",
        "Otros",
    ]


def test_ciclo_completo_con_factura_compartida(entorno) -> None:
    _, plantas, gastos = entorno
    p1 = plantas.registrar(DatosPlanta(marca="Cummins", potencia_kva=50)).id
    p2 = plantas.registrar(DatosPlanta(marca="Perkins", potencia_kva=60)).id
    proveedor = gastos.registrar_proveedor("Filtros del Valle", "900.111.222-3", "602 555 0101")
    factura = gastos.registrar_factura(DatosFactura(proveedor.id, "FE-0042", HOY, 200_000))
    filtros = _categoria(gastos, "Filtros")
    mano_obra = _categoria(gastos, "Mano de obra")

    g1 = gastos.registrar_gasto(
        p1, DatosGasto(filtros, HOY, "Filtro LF3000", 90_000, 2, "Unidad", factura.id)
    )
    gastos.registrar_gasto(
        p2, DatosGasto(filtros, HOY, "Filtro FS1280", 60_000, 1, None, factura.id)
    )
    gastos.registrar_gasto(p1, DatosGasto(mano_obra, HOY, "Cambio de filtros", 50_000))

    # Saldo calculado en SQL
    assert gastos.facturas_con_saldo("0042")[0].saldo_por_asignar == 50_000
    assert gastos.facturas_con_saldo("valle")[0].proveedor_nombre == "Filtros del Valle"

    # Detalle con nombres resueltos en una sola consulta
    detalles = gastos.listar_gastos(p1)
    assert {(d.categoria, d.numero_factura, d.proveedor) for d in detalles} == {
        ("Filtros", "FE-0042", "Filtros del Valle"),
        ("Mano de obra", None, None),
    }

    # Resumen con anulación
    gastos.anular_gasto(g1.id, "Valor mal digitado")
    resumen = gastos.resumen(p1)
    assert (resumen.total, resumen.cantidad, resumen.sin_soporte) == (50_000, 1, 50_000)
    assert gastos.facturas_con_saldo()[0].saldo_por_asignar == 140_000
    anulado = [d for d in gastos.listar_gastos(p1, incluir_anulados=True) if d.gasto.anulado]
    assert anulado[0].gasto.motivo_anulacion == "Valor mal digitado"


def test_datos_del_gasto_se_recuperan_intactos(entorno) -> None:
    _, plantas, gastos = entorno
    planta_id = plantas.registrar(DatosPlanta(marca="Cummins", potencia_kva=50)).id
    datos = DatosGasto(
        _categoria(gastos, "Aceite y lubricantes"), HOY, "Aceite 15W-40", 120_000, 2.5, "Galón"
    )

    registrado = gastos.registrar_gasto(planta_id, datos)

    assert registrado.datos == datos
    assert not registrado.anulado


def test_factura_duplicada_sin_distinguir_mayusculas(entorno) -> None:
    _, _, gastos = entorno
    proveedor = gastos.registrar_proveedor("Filtros del Valle")
    gastos.registrar_factura(DatosFactura(proveedor.id, "FE-0042", HOY, 100_000))
    with pytest.raises(ValidacionError):
        gastos.registrar_factura(DatosFactura(proveedor.id, "fe-0042", HOY, 100_000))


def test_planta_dada_de_baja_rechaza_gastos(entorno) -> None:
    _, plantas, gastos = entorno
    planta_id = plantas.registrar(DatosPlanta(marca="Kohler", potencia_kva=80)).id
    plantas.cambiar_estado(planta_id, E.DADA_DE_BAJA, motivo="Irreparable")
    with pytest.raises(ValidacionError, match="Dada de baja"):
        gastos.registrar_gasto(
            planta_id, DatosGasto(_categoria(gastos, "Repuestos"), HOY, "Pistón", 500_000)
        )


def test_el_esquema_respalda_las_reglas(entorno) -> None:
    """Defensa en profundidad: aunque se salte el servicio, SQLite rechaza datos inválidos."""
    db, plantas, _ = entorno
    planta_id = plantas.registrar(DatosPlanta(marca="Cummins", potencia_kva=50)).id
    with pytest.raises(PersistenciaError), SqliteUnidadDeTrabajo(db) as uow:
        uow.gastos.insertar(planta_id, DatosGasto(1, HOY, "Gasto negativo", -5_000))
