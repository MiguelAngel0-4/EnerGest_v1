"""
Pruebas del nombre sugerido para las hojas de vida.

Ruta: tests/unit/test_nombres_archivo.py
"""

from datetime import date

from src.presentation.controllers.nombres_archivo import nombre_archivo_hoja_vida

HOY = date(2026, 10, 7)


def test_nombre_normal() -> None:
    assert (
        nombre_archivo_hoja_vida("PE-005", "Cummins", "C50D6", HOY)
        == "HV_PE-005_Cummins_C50D6_2026-10-07.pdf"
    )


def test_sin_modelo_y_con_espacios() -> None:
    assert nombre_archivo_hoja_vida("PE-001", "Generac Power", None, HOY) == (
        "HV_PE-001_Generac_Power_2026-10-07.pdf"
    )


def test_quita_caracteres_que_windows_no_admite() -> None:
    nombre = nombre_archivo_hoja_vida("PE-002", 'Marca/Rara:"X"', "M<1>|?*", HOY)
    assert not any(c in nombre for c in '<>:"/\\|?*')
    assert nombre.endswith(".pdf")
