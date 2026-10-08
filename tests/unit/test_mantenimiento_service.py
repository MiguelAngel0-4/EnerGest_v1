"""
Pruebas unitarias de las reglas de mantenimientos (Actividad 4.2).

Ruta: tests/unit/test_mantenimiento_service.py
"""

from dataclasses import replace
from datetime import date

import pytest

from src.business.exceptions import NegocioError, ValidacionError
from src.business.models.estado_planta import EstadoPlanta as E
from src.business.models.gasto import DatosFactura
from src.business.models.mantenimiento import (
    DatosMantenimiento,
    LineaInsumo,
    NivelAlerta,
    TipoMantenimiento,
)
from src.business.models.planta import DatosPlanta
from src.business.services.consecutivo_service import ConsecutivoService
from src.business.services.gasto_service import GastoService
from src.business.services.mantenimiento_service import MantenimientoService
from src.business.services.planta_service import PlantaService
from tests.unit.fakes import AlmacenFake, FakeUnidadDeTrabajo

HOY = date(2026, 10, 9)
FILTROS, ACEITE, MANO_DE_OBRA = 1, 3, 4
PREVENTIVO = TipoMantenimiento.PREVENTIVO


class Servicios:
    def __init__(self) -> None:
        self.hoy = HOY
        almacen = AlmacenFake()
        fabrica = lambda: FakeUnidadDeTrabajo(almacen)  # noqa: E731
        self.plantas = PlantaService(fabrica, ConsecutivoService(), lambda: self.hoy)
        self.gastos = GastoService(fabrica, lambda: self.hoy)
        self.mantenimientos = MantenimientoService(fabrica, lambda: self.hoy)

    def planta(self, horometro: int = 1000) -> int:
        datos = DatosPlanta(marca="Perkins", potencia_kva=60, horometro_inicial=horometro)
        return self.plantas.registrar(datos).id


@pytest.fixture
def s() -> Servicios:
    return Servicios()


def _datos(horometro: int = 1250, fecha: date = HOY, **extra) -> DatosMantenimiento:
    return DatosMantenimiento(fecha, PREVENTIVO, horometro, "Cambio de aceite y filtros", **extra)


INSUMOS = [
    LineaInsumo(FILTROS, "Filtro de aceite LF3000", 45_000),
    LineaInsumo(ACEITE, "Aceite 15W-40", 120_000, 3.5, "Galón"),
    LineaInsumo(MANO_DE_OBRA, "Servicio técnico", 80_000, 1, "Servicio"),
]


# --- Reglas 1, 6: registro con insumos como gastos ----------------------------


def test_registrar_con_insumos_crea_gastos_ligados(s: Servicios) -> None:
    planta_id = s.planta()
    mantenimiento = s.mantenimientos.registrar(planta_id, _datos(tecnico=" J. Pérez "), INSUMOS)

    assert mantenimiento.costo_total == 245_000
    assert mantenimiento.datos.tecnico == "J. Pérez"
    gastos = s.gastos.listar_gastos(planta_id)
    assert len(gastos) == 3
    assert all(g.mantenimiento_fecha == HOY for g in gastos)
    assert s.gastos.resumen(planta_id).total == 245_000


def test_plantas_vendidas_no_admiten_mantenimientos(s: Servicios) -> None:
    planta_id = s.planta()
    s.plantas.cambiar_estado(planta_id, E.DADA_DE_BAJA, motivo="Irreparable")
    with pytest.raises(ValidacionError, match="Dada de baja"):
        s.mantenimientos.registrar(planta_id, _datos())


def test_planta_alquilada_admite_mantenimiento_en_sitio(s: Servicios) -> None:
    planta_id = s.planta()
    s.plantas.cambiar_estado(planta_id, E.ALQUILADA, horometro=1100)
    assert s.mantenimientos.registrar(planta_id, _datos()).planta_id == planta_id


# --- Regla 3: horómetro --------------------------------------------------------


def test_el_horometro_del_mantenimiento_actualiza_la_planta(s: Servicios) -> None:
    planta_id = s.planta(horometro=1000)
    s.mantenimientos.registrar(planta_id, _datos(horometro=1250))
    assert s.plantas.obtener(planta_id).horometro_actual == 1250


def test_horometro_no_puede_retroceder(s: Servicios) -> None:
    planta_id = s.planta(horometro=1000)
    s.plantas.cambiar_estado(planta_id, E.ALQUILADA, horometro=1300)
    with pytest.raises(ValidacionError, match="no puede ser menor"):
        s.mantenimientos.registrar(planta_id, _datos(horometro=1250))


# --- Regla 4: fechas -----------------------------------------------------------


def test_fecha_anterior_al_ultimo_mantenimiento_es_rechazada(s: Servicios) -> None:
    planta_id = s.planta()
    s.mantenimientos.registrar(planta_id, _datos(fecha=date(2026, 10, 5)))
    with pytest.raises(ValidacionError) as error:
        s.mantenimientos.registrar(planta_id, _datos(horometro=1300, fecha=date(2026, 10, 1)))
    assert "fecha" in error.value.errores


# --- Regla 5: programación del próximo -----------------------------------------


def test_proximo_debe_quedar_despues(s: Servicios) -> None:
    datos = _datos(proxima_fecha=HOY, proximo_horometro=1200)
    with pytest.raises(ValidacionError) as error:
        s.mantenimientos.registrar(s.planta(), datos)
    assert set(error.value.errores) == {"proxima_fecha", "proximo_horometro"}


@pytest.mark.parametrize(
    ("fecha", "esperada"),
    [
        (date(2026, 10, 9), date(2027, 4, 9)),
        (date(2026, 8, 31), date(2027, 2, 28)),  # Fin de mes: no existe el 31 de febrero
        (date(2027, 8, 31), date(2028, 2, 29)),  # 2028 es bisiesto
    ],
)
def test_proximo_sugerido_respeta_el_calendario(fecha: date, esperada: date) -> None:
    assert MantenimientoService.proximo_sugerido(fecha, 2075, 6, 250) == (esperada, 2325)


# --- Regla 6: factura y validación de líneas -----------------------------------


def test_insumos_que_superan_la_factura_no_guardan_nada(s: Servicios) -> None:
    planta_id = s.planta()
    proveedor = s.gastos.registrar_proveedor("Filtros del Valle")
    factura = s.gastos.registrar_factura(DatosFactura(proveedor.id, "FE-01", HOY, 100_000))

    with pytest.raises(ValidacionError, match="supera el saldo"):
        s.mantenimientos.registrar(planta_id, _datos(), INSUMOS, factura.id)

    assert s.mantenimientos.listar(planta_id) == []
    assert s.gastos.listar_gastos(planta_id) == []


def test_lineas_invalidas_se_reportan_por_numero(s: Servicios) -> None:
    lineas = [INSUMOS[0], LineaInsumo(FILTROS, "  ", 0)]
    with pytest.raises(ValidacionError) as error:
        s.mantenimientos.registrar(s.planta(), _datos(), lineas)
    assert "Línea 2" in error.value.errores["insumos"]


def test_factura_sin_insumos_es_rechazada(s: Servicios) -> None:
    with pytest.raises(ValidacionError) as error:
        s.mantenimientos.registrar(s.planta(), _datos(), [], factura_id=99)
    assert "factura_id" in error.value.errores


# --- Regla 7: anulación --------------------------------------------------------


def test_anular_anula_sus_gastos_y_su_lectura(s: Servicios) -> None:
    planta_id = s.planta(horometro=1000)
    mantenimiento = s.mantenimientos.registrar(planta_id, _datos(horometro=1250), INSUMOS)

    anulado = s.mantenimientos.anular(mantenimiento.id, "Se registró en la planta equivocada")

    assert anulado.anulado and anulado.costo_total == 0
    assert s.gastos.resumen(planta_id).total == 0
    assert s.plantas.obtener(planta_id).horometro_actual == 1000
    assert s.mantenimientos.listar(planta_id) == []
    with pytest.raises(NegocioError, match="ya estaba anulado"):
        s.mantenimientos.anular(mantenimiento.id, "Otra vez")


def test_anular_exige_motivo(s: Servicios) -> None:
    mantenimiento = s.mantenimientos.registrar(s.planta(), _datos())
    with pytest.raises(ValidacionError):
        s.mantenimientos.anular(mantenimiento.id, "  ")


# --- Alertas --------------------------------------------------------------------


def test_alertas_por_fecha_y_por_horas(s: Servicios) -> None:
    vencida = s.planta()
    proxima_fecha = s.planta()
    proxima_horas = s.planta()
    al_dia = s.planta()
    sin_programar = s.planta()
    s.mantenimientos.registrar(vencida, _datos(proxima_fecha=date(2026, 10, 10)))
    s.mantenimientos.registrar(proxima_fecha, _datos(proxima_fecha=date(2026, 10, 20)))
    s.mantenimientos.registrar(proxima_horas, _datos(proximo_horometro=1260))
    s.mantenimientos.registrar(
        al_dia, _datos(proxima_fecha=date(2027, 4, 9), proximo_horometro=1500)
    )
    s.mantenimientos.registrar(sin_programar, _datos())

    s.hoy = date(2026, 10, 10)  # Pasa un día: la primera vence hoy
    alertas = s.mantenimientos.alertas()

    assert [(a.planta.id, a.nivel) for a in alertas] == [
        (vencida, NivelAlerta.VENCIDO),  # Vencidas primero
        (proxima_fecha, NivelAlerta.PROXIMO),  # Faltan 10 días
        (proxima_horas, NivelAlerta.PROXIMO),  # Faltan 10 horas
    ]
    assert al_dia not in [a.planta.id for a in alertas]
    assert sin_programar not in [a.planta.id for a in alertas]


def test_un_alquiler_puede_vencer_un_mantenimiento_por_horas(s: Servicios) -> None:
    planta_id = s.planta()
    s.mantenimientos.registrar(planta_id, _datos(proximo_horometro=1500))
    assert s.mantenimientos.alertas() == []

    s.plantas.cambiar_estado(planta_id, E.ALQUILADA, horometro=1260)
    s.plantas.cambiar_estado(planta_id, E.DISPONIBLE, horometro=1510)  # Regresa con 1.510 h

    alerta = s.mantenimientos.alertas()[0]
    assert (alerta.nivel, alerta.horas_restantes) == (NivelAlerta.VENCIDO, -10)


def test_solo_cuenta_el_ultimo_mantenimiento_y_plantas_en_operacion(s: Servicios) -> None:
    planta_id = s.planta()
    s.mantenimientos.registrar(planta_id, _datos(proxima_fecha=date(2026, 10, 10)))
    s.mantenimientos.registrar(
        planta_id, replace(_datos(horometro=1300), proxima_fecha=date(2027, 4, 9))
    )
    vendida = s.planta()
    s.mantenimientos.registrar(vendida, _datos(proxima_fecha=date(2026, 10, 10)))
    s.plantas.cambiar_estado(vendida, E.VENDIDA, motivo="Venta")

    assert s.mantenimientos.alertas() == []


def test_tecnicos_sugeridos(s: Servicios) -> None:
    planta_id = s.planta()
    s.mantenimientos.registrar(planta_id, _datos(tecnico="Juan Pérez"))
    s.mantenimientos.registrar(planta_id, _datos(horometro=1300, tecnico="Ana Ruiz"))
    assert s.mantenimientos.tecnicos() == ["Ana Ruiz", "Juan Pérez"]
