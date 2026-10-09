"""
Colores de la identidad visual compartidos por la interfaz y los documentos.

Ruta: src/shared/colores.py

El semáforo de reemplazo debe verse igual en la pestaña Balance y en la hoja
de vida PDF: por eso sus colores viven aquí, en un solo lugar.
"""

from typing import Final

# Nivel del semáforo -> (fondo suave, color principal)
SEMAFORO: Final[dict[str, tuple[str, str]]] = {
    "RENTABLE": ("#E8F5EC", "#2E9E5B"),
    "VIGILAR": ("#FFF6E0", "#C98A00"),
    "EVALUAR_REEMPLAZO": ("#FDECEA", "#C0392B"),
    "SIN_DATOS": ("#F1F3F5", "#6C757D"),
}
