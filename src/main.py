"""
Punto de entrada de EnerGest.

Ruta: src/main.py
Ejecución (desde la raíz del proyecto):  python -m src.main

Este archivo es la "raíz de composición": el ÚNICO lugar donde se
conocen las tres capas a la vez. Como el jefe de obra que reúne a los
distintos contratistas, crea cada pieza y las conecta entre sí; después
de eso, cada capa solo habla con su vecina inmediata.
"""

import logging
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from src.business.services.comercial_service import ComercialService
from src.business.services.consecutivo_service import ConsecutivoService
from src.business.services.gasto_service import GastoService
from src.business.services.hoja_vida_service import HojaVidaService
from src.business.services.mantenimiento_service import MantenimientoService
from src.business.services.planta_service import PlantaService
from src.config import settings
from src.config.logging_config import setup_logging
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.database.exceptions import DatabaseError
from src.infrastructure.reports.pdf_hoja_vida import GeneradorPdfHojaVida
from src.infrastructure.repositories.empresa_json_repository import EmpresaJsonRepository
from src.infrastructure.repositories.sqlite_unidad_de_trabajo import crear_fabrica_uow
from src.presentation.controllers.ficha_controller import FichaPlantaController
from src.presentation.controllers.inventario_controller import InventarioController
from src.presentation.views.equipos.inventario_view import InventarioView
from src.presentation.views.main_window import MainWindow
from src.shared.paths import (
    get_data_dir,
    get_database_path,
    get_resource_path,
    is_using_fallback_location,
)

logger = logging.getLogger(__name__)

_RUTA_ESTILOS = "resources/styles/theme.qss"
_PLANTILLA_EMPRESA = "resources/templates/empresa.json"


def _aplicar_estilos(app: QApplication) -> None:
    """Aplica el estilo Fusion y la hoja QSS. Si falta el archivo, sigue sin estilos."""
    app.setStyle("Fusion")  # Apariencia idéntica en cualquier versión de Windows
    ruta = get_resource_path(_RUTA_ESTILOS)
    try:
        app.setStyleSheet(ruta.read_text(encoding="utf-8"))
    except OSError:
        logger.warning("No se encontró la hoja de estilos en %s; se usan los de Qt.", ruta)


def _preparar_base_de_datos() -> DatabaseManager:
    """Crea el gestor de BD y garantiza que el esquema exista."""
    db = DatabaseManager(get_database_path())
    db.initialize_schema(get_resource_path(settings.SCHEMA_RELATIVE_PATH))
    return db


def main() -> int:
    """Arranca la aplicación y devuelve el código de salida."""
    ruta_log = setup_logging()
    logger.info("Iniciando %s v%s", settings.APP_NAME, settings.APP_VERSION)
    if is_using_fallback_location():
        logger.warning("La carpeta del programa no permite escritura; se usa %%APPDATA%%.")

    app = QApplication(sys.argv)
    app.setApplicationName(settings.APP_NAME)
    app.setApplicationVersion(settings.APP_VERSION)
    _aplicar_estilos(app)

    # --- Capa de datos ---------------------------------------------------
    try:
        db = _preparar_base_de_datos()
    except DatabaseError as exc:
        logger.critical("No se pudo preparar la base de datos: %s", exc)
        QMessageBox.critical(
            None,
            "Error al iniciar",
            f"No se pudo preparar la base de datos.\n\n{exc}\n\n"
            f"Los detalles están en:\n{ruta_log}",
        )
        return 1

    # --- Capa de negocio -------------------------------------------------
    fabrica_uow = crear_fabrica_uow(db)
    servicio_plantas = PlantaService(fabrica_uow, ConsecutivoService())
    empresa = EmpresaJsonRepository(
        get_data_dir() / "empresa.json", get_resource_path(_PLANTILLA_EMPRESA)
    )
    logger.info("Datos de la empresa: %s", empresa.ruta)
    servicio_hojas_vida = HojaVidaService(
        fabrica_uow, GeneradorPdfHojaVida(), empresa.obtener, settings.APP_VERSION
    )
    servicio_gastos = GastoService(fabrica_uow)
    servicio_comercial = ComercialService(fabrica_uow, servicio_plantas)
    servicio_mantenimientos = MantenimientoService(
        fabrica_uow,
        dias_alerta=settings.ALERTA_DIAS_ANTICIPACION,
        horas_alerta=settings.ALERTA_HORAS_ANTICIPACION,
    )

    # --- Capa de presentación --------------------------------------------
    ventana = MainWindow(settings.APP_NAME, settings.APP_VERSION)
    vista_inventario = InventarioView()
    ventana.agregar_vista("inventario", vista_inventario)
    controlador_ficha = FichaPlantaController(
        servicio_plantas,
        servicio_gastos,
        servicio_mantenimientos,
        vista_inventario,
        ventana,
        intervalo_meses=settings.MANTENIMIENTO_INTERVALO_MESES,
        intervalo_horas=settings.MANTENIMIENTO_INTERVALO_HORAS,
        comercial=servicio_comercial,
    )
    controlador_inventario = InventarioController(
        servicio_plantas,
        servicio_hojas_vida,
        vista_inventario,
        ventana,
        ficha=controlador_ficha,
        mantenimientos=servicio_mantenimientos,
        comercial=servicio_comercial,
    )

    ventana.registro_solicitado.connect(controlador_inventario.abrir_registro)
    ventana.set_mensaje_estado(f"Base de datos: {db.db_path}")

    controlador_inventario.recargar()
    ventana.showMaximized()  # Aprovecha toda la pantalla

    codigo = app.exec()
    logger.info("Aplicación cerrada (código %s).", codigo)
    return codigo


if __name__ == "__main__":
    sys.exit(main())
