"""
Pruebas unitarias de alquileres, devoluciones, ventas y cobros (Actividad 4.3).

Ruta: tests/unit/test_comercial_service.py
"""

from datetime import date

import pytest

from src.business.exceptions import NegocioError, TransicionInvalidaError, ValidacionError
from src.business.models.comercial import (
    DatosContrato,
    DatosIngreso,
    DatosVenta,
    ModalidadAlquiler,
    TipoIngreso,
)
from src.business.models.estado_planta import EstadoPlanta as E
from src.business.models.planta import DatosPlanta
from src.business.services.comercial_service import ComercialService
from src.business.services.consecutivo_service import ConsecutivoService
from src.business.services.planta_service import PlantaService
from tests.unit.fakes import AlmacenFake, FakeUnidadDeTrabajo

ENTREGA = date(2026, 10, 1)
DIA, MES = ModalidadAlquiler.DIA, ModalidadAlquiler.MES


class Entorno:
    def __init__(self) -> None:
        self.hoy = ENTREGA
        almacen = AlmacenFake()
        fabrica = lambda: FakeUnidadDeTrabajo(almacen)  # noqa: E731
        self.plantas = PlantaService(fabrica, ConsecutivoService(), lambda: self.hoy)
        self.comercial = ComercialService(fabrica, self.plantas, lambda: self.hoy)
        self.cliente = self.comercial.registrar_cliente(
            "Constructora del Pacífico", "900.555.111-2"
        )
        datos = DatosPlanta(marca="Perkins", potencia_kva=60, horometro_inicial=1000)
        self.planta = self.plantas.registrar(datos).id

    def contrato(self, modalidad=DIA, tarifa: int = 180_000) -> DatosContrato:
        return DatosContrato(self.cliente.id, modalidad, tarifa)


@pytest.fixture
def e() -> Entorno:
    return Entorno()


# --- Alquilar (reglas 1 y 2) ---------------------------------------------------


def test_alquilar_crea_contrato_y_cambia_el_estado(e: Entorno) -> None:
    alquiler = e.comercial.alquilar(e.planta, e.contrato(), horometro=1020)

    assert alquiler.activo and alquiler.fecha_inicio == ENTREGA
    assert e.plantas.obtener(e.planta).estado is E.ALQUILADA
    assert e.comercial.clientes_actuales() == {e.planta: "Constructora del Pacífico"}
    cambios, _ = e.plantas.historial(e.planta)
    assert cambios[-1].alquiler_id == alquiler.id  # La lectura de salida queda ligada


def test_tarifa_y_cliente_son_obligatorios(e: Entorno) -> None:
    with pytest.raises(ValidacionError) as error:
        e.comercial.alquilar(e.planta, e.contrato(tarifa=0), horometro=1020)
    assert "tarifa" in error.value.errores
    with pytest.raises(ValidacionError) as error:
        e.comercial.alquilar(e.planta, DatosContrato(999, DIA, 1000), horometro=1020)
    assert "cliente_id" in error.value.errores


def test_no_se_alquila_una_planta_ya_alquilada(e: Entorno) -> None:
    e.comercial.alquilar(e.planta, e.contrato(), horometro=1020)
    with pytest.raises(TransicionInvalidaError):
        e.comercial.alquilar(e.planta, e.contrato(), horometro=1030)


def test_un_alquiler_fallido_no_deja_contrato(e: Entorno) -> None:
    with pytest.raises(ValidacionError):  # Horómetro menor que el actual: falla el estado
        e.comercial.alquilar(e.planta, e.contrato(), horometro=500)
    assert e.comercial.contrato_activo(e.planta) is None
    assert e.plantas.obtener(e.planta).estado is E.DISPONIBLE


# --- Devolver con liquidación (reglas 3, 4 y 5) --------------------------------


def test_devolver_por_dia_liquida_y_cobra_el_saldo(e: Entorno) -> None:
    e.comercial.alquilar(e.planta, e.contrato(DIA, 180_000), horometro=1020)
    e.hoy = date(2026, 10, 13)

    cerrado = e.comercial.devolver(
        e.planta, horometro=1185, cobrar_saldo=True, numero_documento="CC-0031"
    )

    assert cerrado.valor_liquidado == 12 * 180_000
    assert (cerrado.cobrado, cerrado.saldo, cerrado.horas_uso) == (2_160_000, 0, 165)
    assert e.plantas.obtener(e.planta).estado is E.DISPONIBLE
    ingreso = e.comercial.ingresos(e.planta)[0]
    assert (ingreso.tipo, ingreso.datos.numero_documento) == (TipoIngreso.ALQUILER, "CC-0031")


def test_devolver_por_mes_proporcional_con_anticipo(e: Entorno) -> None:
    alquiler = e.comercial.alquilar(e.planta, e.contrato(MES, 3_000_000), horometro=1020)
    e.hoy = date(2026, 11, 1)
    e.comercial.registrar_cobro(alquiler.id, DatosIngreso(e.hoy, "Mes de octubre", 3_000_000))
    e.hoy = date(2026, 11, 11)

    preliminar = e.comercial.liquidacion_preliminar(e.planta)
    assert preliminar is not None and preliminar[1].valor == 4_000_000  # 1 mes y 10 días

    cerrado = e.comercial.devolver(e.planta, cobrar_saldo=True)
    assert (cerrado.valor_liquidado, cerrado.cobrado, cerrado.saldo) == (4_000_000, 4_000_000, 0)


def test_descuento_negociado_sin_bajar_de_lo_cobrado(e: Entorno) -> None:
    alquiler = e.comercial.alquilar(e.planta, e.contrato(DIA, 100_000), horometro=1020)
    e.hoy = date(2026, 10, 11)
    e.comercial.registrar_cobro(alquiler.id, DatosIngreso(e.hoy, "Anticipo", 500_000))

    with pytest.raises(ValidacionError) as error:
        e.comercial.devolver(e.planta, valor_liquidado=400_000)
    assert "valor_liquidado" in error.value.errores

    cerrado = e.comercial.devolver(e.planta, valor_liquidado=900_000)  # Calculado: 1.000.000
    assert cerrado.saldo == 400_000


def test_saldo_pendiente_se_cobra_despues_sin_excederlo(e: Entorno) -> None:
    alquiler = e.comercial.alquilar(e.planta, e.contrato(DIA, 100_000), horometro=1020)
    e.hoy = date(2026, 10, 6)
    e.comercial.devolver(e.planta)  # Sin cobrar: queda saldo de 500.000

    with pytest.raises(ValidacionError, match="saldo pendiente"):
        e.comercial.registrar_cobro(alquiler.id, DatosIngreso(e.hoy, "Pago", 600_000))
    e.comercial.registrar_cobro(alquiler.id, DatosIngreso(e.hoy, "Pago final", 500_000))
    assert e.comercial.alquileres(e.planta)[0].saldo == 0


def test_dano_durante_el_alquiler_cierra_el_contrato(e: Entorno) -> None:
    e.comercial.alquilar(e.planta, e.contrato(), horometro=1020)
    e.hoy = date(2026, 10, 3)
    cerrado = e.comercial.devolver(e.planta, nuevo_estado=E.EN_MANTENIMIENTO)
    assert not cerrado.activo
    assert e.plantas.obtener(e.planta).estado is E.EN_MANTENIMIENTO


def test_alquiler_antiguo_sin_contrato_solo_cambia_el_estado(e: Entorno) -> None:
    e.plantas.cambiar_estado(e.planta, E.ALQUILADA, horometro=1020)  # Como antes de la 0.7.0
    assert e.comercial.liquidacion_preliminar(e.planta) is None
    assert e.comercial.devolver(e.planta) is None
    assert e.plantas.obtener(e.planta).estado is E.DISPONIBLE


def test_contrato_activo_no_se_salta_con_un_cambio_de_estado_suelto(e: Entorno) -> None:
    e.comercial.alquilar(e.planta, e.contrato(), horometro=1020)
    with pytest.raises(NegocioError, match="contrato de alquiler activo"):
        e.plantas.cambiar_estado(e.planta, E.DISPONIBLE)


# --- Vender ------------------------------------------------------------------


def test_vender_registra_el_ingreso_y_el_estado(e: Entorno) -> None:
    ingreso = e.comercial.vender(e.planta, DatosVenta(e.cliente.id, 42_000_000, "FV-0102"))

    assert (ingreso.tipo, ingreso.datos.valor) == (TipoIngreso.VENTA, 42_000_000)
    planta = e.plantas.obtener(e.planta)
    assert planta.estado is E.VENDIDA and planta.numero_consecutivo is None
    cambios, _ = e.plantas.historial(e.planta)
    assert cambios[-1].motivo == "Venta a Constructora del Pacífico"


def test_venta_sin_precio_no_cambia_nada(e: Entorno) -> None:
    with pytest.raises(ValidacionError):
        e.comercial.vender(e.planta, DatosVenta(e.cliente.id, 0))
    assert e.plantas.obtener(e.planta).estado is E.DISPONIBLE


# --- Reglas 6, 7 y 8 -------------------------------------------------------------


def test_anular_ingreso_devuelve_el_saldo(e: Entorno) -> None:
    alquiler = e.comercial.alquilar(e.planta, e.contrato(DIA, 100_000), horometro=1020)
    e.hoy = date(2026, 10, 3)
    ingreso = e.comercial.registrar_cobro(alquiler.id, DatosIngreso(e.hoy, "Anticipo", 200_000))

    e.comercial.anular_ingreso(ingreso.id, "Consignación rechazada")

    assert e.comercial.contrato_activo(e.planta).cobrado == 0
    with pytest.raises(NegocioError, match="ya estaba anulado"):
        e.comercial.anular_ingreso(ingreso.id, "Otra vez")


def test_condiciones_solo_se_corrigen_con_el_contrato_activo(e: Entorno) -> None:
    alquiler = e.comercial.alquilar(e.planta, e.contrato(DIA, 100_000), horometro=1020)
    corregido = e.comercial.corregir_contrato(alquiler.id, e.contrato(DIA, 120_000))
    assert corregido.tarifa == 120_000

    e.comercial.devolver(e.planta)
    with pytest.raises(NegocioError, match="cerrado"):
        e.comercial.corregir_contrato(alquiler.id, e.contrato(DIA, 150_000))


def test_clientes_unicos_por_nombre_y_documento(e: Entorno) -> None:
    with pytest.raises(ValidacionError) as error:
        e.comercial.registrar_cliente(" constructora del pacífico ", "900.555.111-2")
    assert set(error.value.errores) == {"nombre", "documento"}
