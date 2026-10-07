"""
Pruebas de interfaz de los formularios de plantas.

Ruta: tests/ui/test_formularios.py

Reproducen las observaciones de la validación del MVP 1:
escribir en kW y en el tanque, los campos de filtros y aceite,
y la lectura del horómetro al alquilar.
"""

from datetime import date

import pytest
from PySide6.QtWidgets import QApplication

from src.presentation.dialogs.cambiar_estado_dialog import CambiarEstadoDialog, OpcionEstado
from src.presentation.dialogs.planta_form_dialog import OpcionesFormulario, PlantaFormDialog
from tests.ui.conftest import escribir_como_usuario

OPCIONES = OpcionesFormulario(
    marcas=["Cummins"],
    opciones_fases=[("—", None), ("Trifásica (3)", 3)],
    opciones_combustible=[("—", None), ("Diésel", "DIESEL")],
    opciones_aceite=[("—", None), ("15W-40", "SAE_15W40"), ("25W-60", "SAE_25W60")],
    voltajes=["220 V"],
    sugerencias_filtros={"filtro_aceite": ["Fleetguard LF3000"]},
)


@pytest.fixture
def formulario(qapp: QApplication) -> PlantaFormDialog:
    dialogo = PlantaFormDialog("Registrar", "PE-003", "Disponible", OPCIONES)
    dialogo.show()
    return dialogo


def test_regresion_se_puede_escribir_en_kw_y_tanque(formulario: PlantaFormDialog) -> None:
    """Defecto reportado: 'no deja escribir' en kW ni en capacidad del tanque."""
    escribir_como_usuario(formulario._potencia_kva, "60")
    escribir_como_usuario(formulario._potencia_kw, "48")
    escribir_como_usuario(formulario._capacidad_tanque, "40,5")
    escribir_como_usuario(formulario._horometro, "1200")

    valores = formulario.valores()
    assert valores["potencia_kva"] == 60
    assert valores["potencia_kw"] == 48
    assert valores["capacidad_tanque_gal"] == 40.5
    assert valores["horometro_inicial"] == 1200


def test_campos_numericos_vacios_son_sin_dato(formulario: PlantaFormDialog) -> None:
    valores = formulario.valores()
    assert valores["potencia_kw"] is None
    assert valores["capacidad_tanque_gal"] is None
    assert valores["cantidad_aceite_gal"] is None


def test_filtros_y_aceite_se_leen_del_formulario(formulario: PlantaFormDialog) -> None:
    escribir_como_usuario(formulario._filtros["filtro_aceite"], "Fleetguard LF3000")
    escribir_como_usuario(formulario._filtros["filtro_aire"], "Donaldson P181052")
    escribir_como_usuario(formulario._cantidad_aceite, "2,5")
    formulario._tipo_aceite.setCurrentIndex(formulario._tipo_aceite.findData("SAE_25W60"))

    valores = formulario.valores()
    assert valores["filtro_aceite"] == "Fleetguard LF3000"
    assert valores["filtro_aire"] == "Donaldson P181052"
    assert valores["cantidad_aceite_gal"] == 2.5
    assert valores["tipo_aceite"] == "SAE_25W60"


def test_edicion_carga_y_devuelve_los_mismos_valores(formulario: PlantaFormDialog) -> None:
    originales = formulario.valores() | {
        "marca": "Cummins",
        "potencia_kva": 125.5,
        "potencia_kw": 100.0,
        "valor_compra": 85_000_000,
        "filtro_agua": "WF2071",
        "cantidad_aceite_gal": 3.5,
        "tipo_aceite": "SAE_15W40",
    }
    formulario.cargar_valores(originales)
    assert formulario.valores() == originales


def _dialogo_estado(qapp: QApplication) -> tuple[CambiarEstadoDialog, list[tuple]]:
    opciones = [
        OpcionEstado("ALQUILADA", "Alquilada", False, "", True, True),
        OpcionEstado("EN_MANTENIMIENTO", "En mantenimiento", False, ""),
    ]
    dialogo = CambiarEstadoDialog("PE-001", "Disponible", opciones, date(2026, 1, 1), "1.200 h")
    dialogo.show()
    emitidos: list[tuple] = []
    dialogo.cambio_solicitado.connect(lambda *args: emitidos.append(args))
    return dialogo, emitidos


def test_alquilar_muestra_y_envia_la_lectura_del_horometro(qapp: QApplication) -> None:
    dialogo, emitidos = _dialogo_estado(qapp)
    dialogo._combo.setCurrentIndex(dialogo._combo.findData("ALQUILADA"))
    QApplication.processEvents()

    assert dialogo._fila_horometro.isVisible()
    assert "obligatoria" in dialogo._etiqueta_horometro.text()
    assert dialogo._horometro.text() == ""  # No se pre-llena a propósito

    escribir_como_usuario(dialogo._horometro, "1250")
    dialogo._al_actualizar()
    clave, _motivo, _fecha, horometro = emitidos[-1]
    assert (clave, horometro) == ("ALQUILADA", 1250)


def test_estado_sin_horometro_oculta_el_campo(qapp: QApplication) -> None:
    dialogo, emitidos = _dialogo_estado(qapp)
    dialogo._combo.setCurrentIndex(dialogo._combo.findData("EN_MANTENIMIENTO"))
    QApplication.processEvents()

    assert not dialogo._fila_horometro.isVisible()
    dialogo._al_actualizar()
    assert emitidos[-1][3] is None


def test_el_error_desaparece_al_corregir(qapp: QApplication) -> None:
    dialogo, _ = _dialogo_estado(qapp)
    dialogo._combo.setCurrentIndex(dialogo._combo.findData("ALQUILADA"))
    dialogo.mostrar_errores({"horometro": "La lectura no puede ser menor que la última."})
    assert dialogo._error.isVisible()

    escribir_como_usuario(dialogo._horometro, "1300")
    assert not dialogo._error.isVisible()
