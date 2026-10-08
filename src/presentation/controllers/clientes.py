"""
Creación y listado de clientes, compartidos por los controladores.

Ruta: src/presentation/controllers/clientes.py

Lo usan el inventario (al alquilar o vender desde el cambio de estado) y
la ficha (al registrar un ingreso o corregir un contrato).
"""

import logging
from typing import Any, Protocol

from PySide6.QtWidgets import QDialog, QWidget

from src.business.exceptions import NegocioError, ValidacionError
from src.business.models.comercial import Cliente
from src.business.services.comercial_service import ComercialService
from src.presentation.dialogs.comercial_dialogs import NuevoClienteDialog

logger = logging.getLogger(__name__)


class ConClientes(Protocol):
    """Formulario que ofrece una lista de clientes."""

    def set_clientes(
        self, clientes: list[tuple[str, int]], seleccionar: int | None = None
    ) -> None: ...


def opciones_clientes(comercial: ComercialService) -> list[tuple[str, int]]:
    return [(c.nombre, c.id) for c in comercial.listar_clientes()]


def crear_cliente_desde(formulario: ConClientes, comercial: ComercialService) -> Cliente | None:
    """
    Abre "Nuevo cliente" sobre el formulario y, si se guarda, lo deja seleccionado en él.
    Si hay errores, el diálogo sigue abierto para corregir.
    """
    resultado: dict[str, Any] = {}
    padre = formulario if isinstance(formulario, QWidget) else None
    dialogo = NuevoClienteDialog(padre)

    def guardar(valores: dict[str, Any]) -> None:
        try:
            resultado["cliente"] = comercial.registrar_cliente(
                valores["nombre"], valores["documento"], valores["telefono"]
            )
        except ValidacionError as exc:
            dialogo.marcar_errores(exc.errores)
            return
        except NegocioError as exc:
            dialogo.mostrar_error(str(exc))
            return
        except Exception:
            logger.exception("Error inesperado al crear el cliente.")
            dialogo.mostrar_error("Ocurrió un error inesperado. Los detalles están en el log.")
            return
        dialogo.accept()

    dialogo.guardar_solicitado.connect(guardar)
    aceptado = dialogo.exec() == QDialog.DialogCode.Accepted
    dialogo.deleteLater()
    cliente: Cliente | None = resultado.get("cliente")
    if aceptado and cliente is not None:
        formulario.set_clientes(opciones_clientes(comercial), cliente.id)
        return cliente
    return None
