"""
Pruebas de integración del módulo comercial sobre SQLite real.

Ruta: tests/integration/test_comercial_sqlite.py
"""

from datetime import date
from pathlib import Path

import pytest

from src.business.exceptions import PersistenciaError
from src.business.models.comercial import DatosContrato, DatosIngreso, DatosVenta, ModalidadAlquiler
from src.business.models.estado_planta import EstadoPlanta as E
from src.business.models.planta import DatosPlanta
from src.business.services.comercial_service import ComercialService
from src.business.services.consecutivo_service import ConsecutivoService
from src.business.services.planta_service import PlantaService
from src.config import settings
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.repositories.sqlite_unidad_de_trabajo import (
    SqliteUnidadDeTrabajo,
    crear_fabrica_uow,
)
from src.shared.paths import get_resource_path


class Reloj:
    def __init__(self) -> None:
        self.hoy = date(2026, 10, 1)


@pytest.fixture
def entorno(tmp_path: Path):
    db = DatabaseManager(tmp_path / "comercial.db")
    db.initialize_schema(get_resource_path(settings.SCHEMA_RELATIVE_PATH))
    reloj = Reloj()
    fabrica = crear_fabrica_uow(db)
    plantas = PlantaService(fabrica, ConsecutivoService(), lambda: reloj.hoy)
    comercial = ComercialService(fabrica, plantas, lambda: reloj.hoy)
    planta_id = plantas.registrar(
        DatosPlanta(marca="Perkins", potencia_kva=60, horometro_inicial=1000)
    ).id
    cliente = comercial.registrar_cliente("Eventos del Valle", "1.130.555.444", "315 000 0000")
    return db, reloj, plantas, comercial, planta_id, cliente


def test_ciclo_completo_de_alquiler_mensual_en_sqlite(entorno) -> None:
    _, reloj, plantas, comercial, planta_id, cliente = entorno
    contrato = DatosContrato(cliente.id, ModalidadAlquiler.MES, 3_000_000, "Obra en Jamundí")

    alquiler = comercial.alquilar(planta_id, contrato, horometro=1020)
    assert comercial.clientes_actuales() == {planta_id: "Eventos del Valle"}

    reloj.hoy = date(2026, 11, 1)
    comercial.registrar_cobro(alquiler.id, DatosIngreso(reloj.hoy, "Octubre", 3_000_000, "CC-1"))
    reloj.hoy = date(2026, 11, 11)
    cerrado = comercial.devolver(
        planta_id, horometro=1350, cobrar_saldo=True, numero_documento="CC-2"
    )

    assert (cerrado.valor_liquidado, cerrado.cobrado, cerrado.saldo) == (4_000_000, 4_000_000, 0)
    assert cerrado.horas_uso == 330  # Calculado en SQL con las lecturas ligadas al contrato
    assert cerrado.observaciones == "Obra en Jamundí"
    assert comercial.clientes_actuales() == {}
    assert plantas.obtener(planta_id).horometro_actual == 1350
    assert [i.datos.numero_documento for i in comercial.ingresos(planta_id)] == ["CC-2", "CC-1"]


def test_venta_en_sqlite(entorno) -> None:
    _, _, plantas, comercial, planta_id, cliente = entorno
    comercial.vender(planta_id, DatosVenta(cliente.id, 42_000_000, "FV-0102"))
    venta = comercial.ingresos(planta_id)[0]
    assert (venta.cliente_nombre, venta.datos.valor) == ("Eventos del Valle", 42_000_000)
    assert plantas.obtener(planta_id).estado is E.VENDIDA


def test_anulacion_en_sqlite(entorno) -> None:
    _, reloj, _, comercial, planta_id, cliente = entorno
    alquiler = comercial.alquilar(
        planta_id, DatosContrato(cliente.id, ModalidadAlquiler.DIA, 1000), 1020
    )
    reloj.hoy = date(2026, 10, 2)
    ingreso = comercial.registrar_cobro(alquiler.id, DatosIngreso(reloj.hoy, "Anticipo", 500))
    comercial.anular_ingreso(ingreso.id, "Error de digitación")
    assert comercial.contrato_activo(planta_id).cobrado == 0
    assert comercial.ingresos(planta_id, incluir_anulados=True)[0].anulado


def test_el_esquema_impide_dos_contratos_activos(entorno) -> None:
    """Defensa en profundidad: aunque se salte el servicio, SQLite lo rechaza."""
    db, _, _, comercial, planta_id, cliente = entorno
    contrato = DatosContrato(cliente.id, ModalidadAlquiler.DIA, 1000)
    comercial.alquilar(planta_id, contrato, horometro=1020)
    with pytest.raises(PersistenciaError), SqliteUnidadDeTrabajo(db) as uow:
        uow.alquileres.insertar(planta_id, contrato, date(2026, 10, 1))
