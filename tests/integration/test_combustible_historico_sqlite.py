"""
Una planta con Gas guardada en una base real se lee y se edita sin perder el dato.

Ruta: tests/integration/test_combustible_historico_sqlite.py
"""

from dataclasses import replace
from datetime import date
from pathlib import Path

from src.business.models.planta import TipoCombustible
from src.business.services.consecutivo_service import ConsecutivoService
from src.business.services.planta_service import PlantaService
from src.config import settings
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.repositories.sqlite_unidad_de_trabajo import crear_fabrica_uow
from src.shared.paths import get_resource_path


def test_planta_historica_con_gas_se_conserva(tmp_path: Path) -> None:
    db = DatabaseManager(tmp_path / "historico.db")
    db.initialize_schema(get_resource_path(settings.SCHEMA_RELATIVE_PATH))
    with db.transaction() as conn:  # Registro anterior a la decisión de retirar el Gas
        conn.execute(
            "INSERT INTO plantas (numero_consecutivo, marca, potencia_kva, tipo_combustible) "
            "VALUES (1, 'Kohler', 30, 'GAS')"
        )
    servicio = PlantaService(crear_fabrica_uow(db), ConsecutivoService(), lambda: date(2026, 9, 30))

    planta = servicio.listar()[0]
    editada = servicio.actualizar_datos(planta.id, replace(planta.datos, modelo="KG30"))

    assert editada.datos.tipo_combustible is TipoCombustible.GAS
    assert editada.datos.modelo == "KG30"
