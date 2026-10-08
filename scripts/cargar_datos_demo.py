"""
Carga plantas de ejemplo para probar y validar la interfaz.

Ruta: scripts/cargar_datos_demo.py
Uso (desde la raíz del proyecto):  python -m scripts.cargar_datos_demo

Registra las plantas A TRAVÉS DEL SERVICIO (no con SQL directo), así que
todas las reglas de negocio se aplican igual que en la aplicación real.
Solo carga datos si la base de datos está vacía.
"""

import logging
import sys
from datetime import date

from src.business.models.comercial import DatosContrato, DatosVenta, ModalidadAlquiler
from src.business.models.estado_planta import EstadoPlanta
from src.business.models.planta import DatosPlanta, TipoAceite, TipoCombustible
from src.business.services.comercial_service import ComercialService
from src.business.services.consecutivo_service import ConsecutivoService
from src.business.services.planta_service import PlantaService
from src.config import settings
from src.config.logging_config import setup_logging
from src.infrastructure.database.connection import DatabaseManager
from src.infrastructure.repositories.sqlite_unidad_de_trabajo import crear_fabrica_uow
from src.shared.paths import get_database_path, get_resource_path

D = TipoCombustible.DIESEL
G = TipoCombustible.GASOLINA

# (marca, modelo, serie, kVA, kW, voltaje, fases, combustible, tanque, fecha, valor, horómetro)
_PLANTAS_DEMO: list[tuple] = [
    (
        "Caterpillar",
        "C9.3",
        "CAT-12345",
        250,
        200,
        "110/220 V",
        3,
        D,
        120,
        date(2022, 3, 15),
        185_000_000,
        1200,
    ),
    (
        "Generac",
        "SD150",
        "GEN-98765",
        150,
        120,
        "110/220 V",
        3,
        D,
        80,
        date(2023, 1, 10),
        98_000_000,
        800,
    ),
    (
        "Cummins",
        "C50D6",
        "CUM-50211",
        50,
        40,
        "110/220 V",
        3,
        D,
        45,
        date(2021, 7, 2),
        42_000_000,
        3100,
    ),
    (
        "Perkins",
        "P110",
        "PER-11034",
        110,
        88,
        "110/220 V",
        3,
        D,
        60,
        date(2022, 11, 20),
        76_500_000,
        2050,
    ),
    (
        "Honda",
        "EU7000is",
        "HON-70001",
        7,
        5.5,
        "110/220 V",
        1,
        G,
        5,
        date(2024, 2, 14),
        18_900_000,
        340,
    ),
    (
        "Generac",
        "SD030",
        "GEN-30120",
        30,
        24,
        "110/220 V",
        1,
        D,
        30,
        date(2023, 6, 5),
        31_000_000,
        1200,
    ),
    (
        "Kohler",
        "KD800",
        "KOH-80077",
        800,
        640,
        "110/220 V",
        3,
        D,
        400,
        date(2020, 9, 1),
        520_000_000,
        6400,
    ),
    (
        "Caterpillar",
        "C4.4",
        "CAT-70450",
        70,
        56,
        "110/220 V",
        3,
        D,
        50,
        date(2023, 4, 18),
        58_000_000,
        900,
    ),
    (
        "Perkins",
        "P33",
        "PER-33001",
        33,
        26,
        "110/220 V",
        1,
        D,
        35,
        date(2024, 8, 9),
        29_500_000,
        150,
    ),
    (
        "Cummins",
        "C150D6",
        "CUM-15088",
        150,
        120,
        "110/220 V",
        3,
        D,
        90,
        date(2021, 12, 1),
        101_000_000,
        4700,
    ),
    (
        "Generac",
        "SD050",
        "GEN-50066",
        50,
        40,
        "110/220 V",
        3,
        D,
        40,
        date(2024, 1, 22),
        39_000_000,
        610,
    ),
    (
        "Kohler",
        "KD200",
        "KOH-20019",
        200,
        160,
        "110/220 V",
        3,
        D,
        110,
        date(2022, 5, 30),
        140_000_000,
        2800,
    ),
]

# Filtros y aceite por serial: (aceite, combustible/separador, agua, aire, galones, tipo)
_CONSUMIBLES_DEMO: dict[str, tuple[str, str, str, str, float, TipoAceite]] = {
    "CAT-12345": (
        "CAT 1R-0739",
        "CAT 1R-0762",
        "CAT 9N-3368",
        "CAT 6I-2501",
        7.5,
        TipoAceite.SAE_15W40,
    ),
    "GEN-98765": (
        "Fleetguard LF3000",
        "Fleetguard FS1280",
        "Fleetguard WF2071",
        "Donaldson P181052",
        4.0,
        TipoAceite.SAE_15W40,
    ),
    "PER-11034": (
        "Perkins 2654407",
        "Perkins 26560201",
        "Fleetguard WF2073",
        "Donaldson P822768",
        3.5,
        TipoAceite.SAE_25W60,
    ),
    "CUM-15088": (
        "Fleetguard LF3000",
        "Fleetguard FS1280",
        "Fleetguard WF2071",
        "Donaldson P181052",
        4.0,
        TipoAceite.SAE_15W40,
    ),
}

# Clientes de demostración: (nombre, NIT o cédula, teléfono)
_CLIENTES_DEMO: list[tuple[str, str, str]] = [
    ("Constructora del Pacífico S.A.S.", "900.555.111-2", "602 555 1111"),
    ("Eventos del Valle", "1.130.555.444", "315 000 0000"),
    ("Agroindustrias del Cauca S.A.S.", "800.222.333-4", "602 555 2222"),
]

# Alquileres con contrato: (posición de la planta, cliente, modalidad, tarifa, horómetro)
_ALQUILERES_DEMO: list[tuple[int, int, ModalidadAlquiler, int, int]] = [
    (1, 0, ModalidadAlquiler.MES, 3_000_000, 820),
    (3, 1, ModalidadAlquiler.DIA, 180_000, 2075),
]

# Otros cambios de estado: (posición de la planta, nuevo estado, motivo)
_EVENTOS_DEMO: list[tuple[int, EstadoPlanta, str]] = [
    (5, EstadoPlanta.EN_MANTENIMIENTO, "Revisión del sistema de arranque"),
    (6, EstadoPlanta.DADA_DE_BAJA, "Motor fundido; reparación no rentable"),
    (10, EstadoPlanta.RETIRADA, "Sin demanda; almacenada en bodega"),
]

# Venta con precio: (posición de la planta, cliente, precio, documento)
_VENTA_DEMO: tuple[int, int, int, str] = (2, 2, 42_000_000, "FV-0102")


def main() -> int:
    setup_logging(logging.INFO)
    db = DatabaseManager(get_database_path())
    db.initialize_schema(get_resource_path(settings.SCHEMA_RELATIVE_PATH))
    fabrica = crear_fabrica_uow(db)
    servicio = PlantaService(fabrica, ConsecutivoService())
    comercial = ComercialService(fabrica, servicio)

    if servicio.listar(incluir_fuera_de_operacion=True):
        print("La base de datos ya tiene plantas; no se cargaron datos de demostración.")
        return 0

    plantas = []
    for fila in _PLANTAS_DEMO:
        marca, modelo, serie, kva, kw, voltaje, fases, comb, tanque, fecha, valor, horas = fila
        aceite = combustible = agua = aire = None
        galones: float | None = None
        tipo_aceite: TipoAceite | None = None
        if serie in _CONSUMIBLES_DEMO:
            aceite, combustible, agua, aire, galones, tipo_aceite = _CONSUMIBLES_DEMO[serie]
        plantas.append(
            servicio.registrar(
                DatosPlanta(
                    marca=marca,
                    modelo=modelo,
                    numero_serie=serie,
                    potencia_kva=kva,
                    potencia_kw=kw,
                    voltaje=voltaje,
                    fases=fases,
                    tipo_combustible=comb,
                    capacidad_tanque_gal=tanque,
                    fecha_adquisicion=fecha,
                    valor_compra=valor,
                    horometro_inicial=horas,
                    filtro_aceite=aceite,
                    filtro_combustible=combustible,
                    filtro_agua=agua,
                    filtro_aire=aire,
                    cantidad_aceite_gal=galones,
                    tipo_aceite=tipo_aceite,
                )
            )
        )

    # Todo pasa por los servicios: cada dato de ejemplo respeta las mismas reglas.
    clientes = [comercial.registrar_cliente(*datos) for datos in _CLIENTES_DEMO]
    for posicion, cliente, modalidad, tarifa, horometro in _ALQUILERES_DEMO:
        contrato = DatosContrato(clientes[cliente].id, modalidad, tarifa)
        comercial.alquilar(plantas[posicion].id, contrato, horometro)
    for posicion, estado, motivo in _EVENTOS_DEMO:
        servicio.cambiar_estado(plantas[posicion].id, estado, motivo=motivo)
    posicion, cliente, precio, documento = _VENTA_DEMO
    comercial.vender(plantas[posicion].id, DatosVenta(clientes[cliente].id, precio, documento))

    print(f"Se cargaron {len(plantas)} plantas de demostración en {db.db_path}")
    print(f"Números libres: {servicio.numeros_libres()} | Próximo: {servicio.proximo_numero()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
