"""
Pruebas de integración del módulo de mantenimientos sobre SQLite real.

Ruta: tests/integration/test_mantenimientos_sqlite.py
"""

from datetime import date
from pathlib import Path

import pytest

from src.business.exceptions import PersistenciaError
from src.business.models.mantenimiento import (
    DatosMantenimiento,
    LineaInsumo,
    NivelAlerta,
    TipoMantenimiento,
)
from src.business.models.planta import DatosPlanta
from src.business.services.consecutivo_service import ConsecutivoService
from src.business.services.gasto_service import GastoService
from src.business.services.mantenimiento_service import MantenimientoService
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
def entorno(tmp_path: Path):
    db = DatabaseManager(tmp_path / "mant.db")
    db.initialize_schema(get_resource_path(settings.SCHEMA_RELATIVE_PATH))
    fabrica = crear_fabrica_uow(db)
    plantas = PlantaService(fabrica, ConsecutivoService(), lambda: HOY)
    gastos = GastoService(fabrica, lambda: HOY)
    planta_id = plantas.registrar(
        DatosPlanta(marca="Perkins", potencia_kva=60, horometro_inicial=2000)
    ).id
    return db, plantas, gastos, MantenimientoService(fabrica, lambda: HOY), planta_id


def _categoria(gastos: GastoService, nombre: str) -> int:
    return next(c.id for c in gastos.listar_categorias() if c.nombre == nombre)


def test_ciclo_completo_en_sqlite(entorno) -> None:
    _, plantas, gastos, mantenimientos, planta_id = entorno
    insumos = [
        LineaInsumo(_categoria(gastos, "Filtros"), "Filtro LF3000", 45_000),
        LineaInsumo(
            _categoria(gastos, "Aceite y lubricantes"), "Aceite 25W-60", 130_000, 3.5, "Galón"
        ),
    ]
    datos = DatosMantenimiento(
        HOY,
        TipoMantenimiento.PREVENTIVO,
        2075,
        "Cambio de aceite y filtros",
        "Juan Pérez",
        date(2027, 4, 9),
        2325,
    )

    registrado = mantenimientos.registrar(planta_id, datos, insumos)

    assert registrado.datos == datos  # Ida y vuelta sin pérdida
    assert registrado.costo_total == 175_000
    assert plantas.obtener(planta_id).horometro_actual == 2075  # Cuenta en el SQL
    detalles = gastos.listar_gastos(planta_id)
    assert {d.mantenimiento_fecha for d in detalles} == {HOY}
    assert mantenimientos.tecnicos() == ["Juan Pérez"]

    mantenimientos.anular(registrado.id, "Datos equivocados")
    assert plantas.obtener(planta_id).horometro_actual == 2000  # La lectura deja de contar
    assert gastos.resumen(planta_id).total == 0
    anulados = gastos.listar_gastos(planta_id, incluir_anulados=True)
    assert all(d.gasto.motivo_anulacion.startswith("Mantenimiento anulado") for d in anulados)


def test_alertas_calculadas_desde_sqlite(entorno) -> None:
    _, plantas, _, mantenimientos, planta_id = entorno
    otra = plantas.registrar(DatosPlanta(marca="Cummins", potencia_kva=50)).id
    mantenimientos.registrar(
        planta_id,
        DatosMantenimiento(
            HOY, TipoMantenimiento.PREVENTIVO, 2075, "Preventivo", proximo_horometro=2090
        ),
    )
    mantenimientos.registrar(
        otra,
        DatosMantenimiento(
            HOY, TipoMantenimiento.CORRECTIVO, 10, "Correctivo", proxima_fecha=date(2026, 10, 12)
        ),
    )

    alertas = mantenimientos.alertas()

    assert [(a.planta.id, a.nivel, a.horas_restantes, a.dias_restantes) for a in alertas] == [
        (planta_id, NivelAlerta.PROXIMO, 15, None),  # PE-001
        (otra, NivelAlerta.PROXIMO, None, 3),  # PE-002
    ]


def test_el_esquema_rechaza_un_proximo_menor_que_la_lectura(entorno) -> None:
    db, _, _, _, planta_id = entorno
    datos = DatosMantenimiento(HOY, TipoMantenimiento.PREVENTIVO, 2075, "x", proximo_horometro=2000)
    with pytest.raises(PersistenciaError), SqliteUnidadDeTrabajo(db) as uow:
        uow.mantenimientos.insertar(planta_id, datos)  # Saltando el servicio a propósito
