"""
Pruebas de interfaz de la pestaña Balance (Actividad 4.4).

Ruta: tests/ui/test_balance_ui.py

El recorrido usa SQLite real: las consultas de reporte viven en SQL.
"""

from datetime import date
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from src.business.models.gasto import DatosGasto
from src.business.models.planta import DatosPlanta
from src.business.services.comercial_service import ComercialService
from src.business.services.consecutivo_service import ConsecutivoService
from src.business.services.gasto_service import GastoService
from src.business.services.mantenimiento_service import MantenimientoService
from src.business.services.planta_service import PlantaService
from src.business.services.rentabilidad_service import RentabilidadService
from src.config import settings
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.repositories.sqlite_unidad_de_trabajo import crear_fabrica_uow
from src.presentation.controllers.ficha_controller import FichaPlantaController
from src.presentation.dialogs.ficha_planta_dialog import FichaPlantaDialog
from src.presentation.widgets.balance_widget import BalanceWidget, FilaBalance
from src.shared.paths import get_resource_path


def _textos(widget: QWidget) -> list[str]:
    return [etiqueta.text() for etiqueta in widget.findChildren(QLabel)]


def test_semaforo_y_cifras(qapp: QApplication) -> None:
    pestana = BalanceWidget()
    pestana.show()
    pestana.mostrar_semaforo("EVALUAR_REEMPLAZO", "EVALUAR REEMPLAZO", ["Razón uno", "Razón dos"])
    pestana.mostrar_cifras([FilaBalance("Resultado", "-$ 1.000", negativo=True)])
    QApplication.processEvents()
    textos = _textos(pestana)
    assert "EVALUAR REEMPLAZO" in textos
    assert any("Razón dos" in t for t in textos)
    rojo = next(e for e in pestana.findChildren(QLabel) if e.text() == "-$ 1.000")
    assert "#C0392B" in rojo.styleSheet()


def test_el_rango_muestra_sus_fechas(qapp: QApplication) -> None:
    pestana = BalanceWidget()
    pestana.show()
    assert not pestana._desde.isVisible()
    pestana._periodo.setCurrentIndex(pestana._periodo.findData("RANGO"))
    assert pestana._desde.isVisible() and pestana._hasta.isVisible()


@pytest.fixture
def servicios(qapp: QApplication, tmp_path: Path):
    db = DatabaseManager(tmp_path / "balance.db")
    db.initialize_schema(get_resource_path(settings.SCHEMA_RELATIVE_PATH))
    fabrica = crear_fabrica_uow(db)
    plantas = PlantaService(fabrica, ConsecutivoService())
    gastos = GastoService(fabrica)
    rentabilidad = RentabilidadService(fabrica)
    ficha = FichaPlantaController(
        plantas,
        gastos,
        MantenimientoService(fabrica),
        QWidget(),
        comercial=ComercialService(fabrica, plantas),
        rentabilidad=rentabilidad,
    )
    planta = plantas.registrar(
        DatosPlanta(marca="Perkins", potencia_kva=60, valor_compra=1_000_000)
    ).id
    repuestos = next(c.id for c in gastos.listar_categorias() if c.nombre == "Repuestos")
    gastos.registrar_gasto(planta, DatosGasto(repuestos, date.today(), "Motor", 700_000))
    return ficha, planta


def test_balance_desde_la_ficha(servicios, monkeypatch) -> None:
    ficha, planta = servicios
    observado: dict = {}

    def usuario_mira_el_balance(dialogo: FichaPlantaDialog) -> int:
        observado["todo"] = _textos(dialogo.balance)
        pestana = dialogo.balance
        pestana._periodo.setCurrentIndex(pestana._periodo.findData("ANIO"))
        QApplication.processEvents()
        observado["anio"] = _textos(dialogo.balance)
        return 1

    monkeypatch.setattr(FichaPlantaDialog, "exec", usuario_mira_el_balance)
    ficha.abrir(planta, "Balance")

    todo = observado["todo"]
    assert "EVALUAR REEMPLAZO" in todo  # 70 % de desgaste y pérdida reciente
    assert "70 %" in todo
    assert "-$ 1.700.000" in todo or "$ -1.700.000" in " ".join(todo)  # Recuperación
    assert any("Le faltan" in t for t in todo)
    # En un período parcial, la recuperación no se calcula (sería engañosa)
    assert any("Se calcula al consultar todo el historial" in t for t in observado["anio"])
