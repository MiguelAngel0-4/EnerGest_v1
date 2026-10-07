"""
Pruebas unitarias de PlantaService (sin base de datos).

Ruta: tests/unit/test_planta_service.py

Usan repositorios en memoria y un reloj fijo, así que verifican
SOLO las reglas de negocio, de forma rápida y repetible.
"""

from datetime import date

import pytest

from src.business.exceptions import (
    PlantaNoEncontradaError,
    TransicionInvalidaError,
    ValidacionError,
)
from src.business.models.estado_planta import EstadoPlanta as E
from src.business.models.planta import DatosPlanta
from src.business.services.consecutivo_service import ConsecutivoService
from src.business.services.planta_service import PlantaService
from tests.unit.fakes import AlmacenFake, FakeUnidadDeTrabajo

HOY = date(2026, 9, 30)


def _datos(marca: str = "Cummins", serie: str | None = None) -> DatosPlanta:
    return DatosPlanta(marca=marca, potencia_kva=100, numero_serie=serie)


@pytest.fixture
def almacen() -> AlmacenFake:
    return AlmacenFake()


@pytest.fixture
def servicio(almacen: AlmacenFake) -> PlantaService:
    return PlantaService(
        uow_factory=lambda: FakeUnidadDeTrabajo(almacen),
        consecutivos=ConsecutivoService(),
        hoy=lambda: HOY,  # Reloj fijo
    )


# --- Registro ----------------------------------------------------------------


def test_registrar_asigna_consecutivos_en_orden(servicio: PlantaService) -> None:
    p1 = servicio.registrar(_datos())
    p2 = servicio.registrar(_datos())
    assert (p1.numero_consecutivo, p2.numero_consecutivo) == (1, 2)
    assert p1.estado is E.DISPONIBLE


def test_registrar_crea_historiales(servicio: PlantaService) -> None:
    planta = servicio.registrar(_datos())
    cambios, consecutivos = servicio.historial(planta.id)
    assert cambios[0].estado_anterior is None and cambios[0].estado_nuevo is E.DISPONIBLE
    assert consecutivos[0].numero == 1 and consecutivos[0].vigente


def test_registrar_con_datos_invalidos(servicio: PlantaService, almacen: AlmacenFake) -> None:
    with pytest.raises(ValidacionError) as error:
        servicio.registrar(DatosPlanta(marca="", potencia_kva=0))
    assert set(error.value.errores) == {"marca", "potencia_kva"}
    assert almacen.plantas == {}


def test_numero_de_serie_duplicado(servicio: PlantaService) -> None:
    servicio.registrar(_datos(serie="ABC-123"))
    with pytest.raises(ValidacionError) as error:
        servicio.registrar(_datos(serie="ABC-123"))
    assert "numero_serie" in error.value.errores


def test_varias_plantas_sin_serie_son_validas(servicio: PlantaService) -> None:
    servicio.registrar(_datos(serie="  "))
    servicio.registrar(_datos(serie=""))
    assert len(servicio.listar()) == 2


# --- Cambios de estado y consecutivos -----------------------------------------


def test_vender_libera_numero_y_se_reutiliza(servicio: PlantaService) -> None:
    servicio.registrar(_datos())  # 1
    p2 = servicio.registrar(_datos())  # 2
    servicio.registrar(_datos())  # 3

    vendida = servicio.cambiar_estado(p2.id, E.VENDIDA, motivo="Venta a cliente")
    nueva = servicio.registrar(_datos(marca="Perkins"))

    assert vendida.numero_consecutivo is None
    assert nueva.numero_consecutivo == 2  # Reutiliza el hueco
    assert [r.planta_id for r in servicio.quienes_tuvieron_numero(2)] == [p2.id, nueva.id]


def test_motivo_obligatorio_al_salir_de_operacion(servicio: PlantaService) -> None:
    planta = servicio.registrar(_datos())
    with pytest.raises(ValidacionError) as error:
        servicio.cambiar_estado(planta.id, E.VENDIDA, motivo="   ")
    assert "motivo" in error.value.errores


def test_alquilar_con_lectura_no_requiere_motivo_ni_cambia_numero(
    servicio: PlantaService,
) -> None:
    planta = servicio.registrar(_datos())
    alquilada = servicio.cambiar_estado(planta.id, E.ALQUILADA, horometro=150)
    assert alquilada.estado is E.ALQUILADA
    assert alquilada.numero_consecutivo == 1


def test_transicion_invalida(servicio: PlantaService) -> None:
    planta = servicio.registrar(_datos())
    servicio.cambiar_estado(planta.id, E.ALQUILADA, horometro=150)
    with pytest.raises(TransicionInvalidaError):
        servicio.cambiar_estado(planta.id, E.VENDIDA, motivo="Venta")


def test_fecha_futura_rechazada(servicio: PlantaService) -> None:
    planta = servicio.registrar(_datos())
    with pytest.raises(ValidacionError) as error:
        servicio.cambiar_estado(planta.id, E.ALQUILADA, fecha=date(2026, 10, 1), horometro=150)
    assert "fecha" in error.value.errores


def test_fecha_anterior_al_ultimo_cambio_rechazada(servicio: PlantaService) -> None:
    planta = servicio.registrar(_datos())  # Registrada el 2026-09-30
    with pytest.raises(ValidacionError):
        servicio.cambiar_estado(planta.id, E.ALQUILADA, fecha=date(2026, 9, 1), horometro=150)


def test_reactivar_recupera_su_numero_si_esta_libre(servicio: PlantaService) -> None:
    planta = servicio.registrar(_datos())
    servicio.cambiar_estado(planta.id, E.RETIRADA, motivo="A bodega")
    reactivada = servicio.cambiar_estado(planta.id, E.DISPONIBLE)
    assert reactivada.numero_consecutivo == 1


def test_reactivar_recibe_menor_libre_si_su_numero_fue_tomado(servicio: PlantaService) -> None:
    p1 = servicio.registrar(_datos())  # 1
    servicio.registrar(_datos())  # 2
    servicio.cambiar_estado(p1.id, E.RETIRADA, motivo="A bodega")
    servicio.registrar(_datos())  # Toma el 1
    reactivada = servicio.cambiar_estado(p1.id, E.DISPONIBLE)
    assert reactivada.numero_consecutivo == 3


def test_planta_inexistente(servicio: PlantaService) -> None:
    with pytest.raises(PlantaNoEncontradaError):
        servicio.obtener(999)


# --- Consultas ---------------------------------------------------------------


def test_listar_por_defecto_oculta_plantas_fuera_de_operacion(servicio: PlantaService) -> None:
    p1 = servicio.registrar(_datos())
    servicio.registrar(_datos())
    servicio.cambiar_estado(p1.id, E.DADA_DE_BAJA, motivo="Motor fundido")

    assert len(servicio.listar()) == 1
    assert len(servicio.listar(incluir_fuera_de_operacion=True)) == 2


def test_listar_busca_por_texto(servicio: PlantaService) -> None:
    servicio.registrar(_datos(marca="Cummins"))
    servicio.registrar(_datos(marca="Perkins"))
    assert [p.datos.marca for p in servicio.listar(texto=" perk ")] == ["Perkins"]


# --- Atomicidad --------------------------------------------------------------


def test_error_a_mitad_de_operacion_no_deja_cambios_parciales(
    servicio: PlantaService, almacen: AlmacenFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fallar(*_args: object) -> None:
        raise RuntimeError("Falla simulada al escribir el historial")

    monkeypatch.setattr(
        "tests.unit.fakes.FakeHistorialEstadoRepository.registrar", fallar
    )
    with pytest.raises(RuntimeError):
        servicio.registrar(_datos())

    assert almacen.plantas == {}
    assert almacen.consecutivos == []
