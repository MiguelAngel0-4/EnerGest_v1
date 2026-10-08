"""
Nombres de archivo sugeridos para los documentos.

Ruta: src/presentation/controllers/nombres_archivo.py

Sin dependencias de Qt, para poder probarlo como una función normal.
"""

import re
from datetime import date

# Caracteres que Windows no admite en nombres de archivo.
_INVALIDOS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_LARGO_MAXIMO = 120


def nombre_archivo_hoja_vida(numero: str, marca: str, modelo: str | None, fecha: date) -> str:
    """
    Ej.: ("PE-005", "Cummins", "C50D6", 2026-10-07) -> "HV_PE-005_Cummins_C50D6_2026-10-07.pdf"

    El número va primero y la fecha en formato AAAA-MM-DD: así, en una carpeta
    ordenada por nombre, las hojas de una misma planta quedan juntas y en orden.
    """
    partes = ["HV", numero, marca, modelo or "", fecha.isoformat()]
    texto = "_".join(parte.strip() for parte in partes if parte and parte.strip())
    texto = _INVALIDOS.sub("", texto)
    texto = re.sub(r"\s+", "_", texto)
    return f"{texto[:_LARGO_MAXIMO]}.pdf"
