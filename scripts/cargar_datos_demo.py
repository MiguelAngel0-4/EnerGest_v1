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

from src.business.models.estado_planta import EstadoPlanta
from src.business.models.planta import DatosPlanta, TipoCombustible
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
    ("Caterpillar", "C9.3", "CAT-12345", 250, 200, "220/440 V", 3, D, 120, date(2022, 3, 15), 185_000_000, 1200),
    ("Generac", "SD150", "GEN-98765", 150, 120, "120/240 V", 3, D, 80, date(2023, 1, 10), 98_000_000, 800),
    ("Cummins", "C50D6", "CUM-50211", 50, 40, "120/240 V", 3, D, 45, date(2021, 7, 2), 42_000_000, 3100),
    ("Perkins", "P110", "PER-11034", 110, 88, "220/440 V", 3, D, 60, date(2022, 11, 20), 76_500_000, 2050),
    ("Honda", "EU7000is", "HON-70001", 7, 5.5, "120/240 V", 1, G, 5, date(2024, 2, 14), 18_900_000, 340),
    ("Generac", "SD030", "GEN-30120", 30, 24, "120/240 V", 1, D, 30, date(2023, 6, 5), 31_000_000, 1200),
    ("Kohler", "KD800", "KOH-80077", 800, 640, "440 V", 3, D, 400, date(2020, 9, 1), 520_000_000, 6400),
    ("Caterpillar", "C4.4", "CAT-70450", 70, 56, "220 V", 3, D, 50, date(2023, 4, 18), 58_000_000, 900),
    ("Perkins", "P33", "PER-33001", 33, 26, "120/240 V", 1, D, 35, date(2024, 8, 9), 29_500_000, 150),
    ("Cummins", "C150D6", "CUM-15088", 150, 120, "220/440 V", 3, D, 90, date(2021, 12, 1), 101_000_000, 4700),
    ("Generac", "SD050", "GEN-50066", 50, 40, "120/240 V", 3, D, 40, date(2024, 1, 22), 39_000_000, 610),
    ("Kohler", "KD200", "KOH-20019", 200, 160, "220/440 V", 3, D, 110, date(2022, 5, 30), 140_000_000, 2800),
]

# (posición de la planta en la lista, nuevo estado, motivo)
_EVENTOS_DEMO: list[tuple[int, EstadoPlanta, str | None]] = [
    (1, EstadoPlanta.ALQUILADA, None),
    (3, EstadoPlanta.ALQUILADA, None),
    (5, EstadoPlanta.EN_MANTENIMIENTO, None),
    (2, EstadoPlanta.VENDIDA, "Venta a Constructora del Valle"),
    (6, EstadoPlanta.DADA_DE_BAJA, "Motor fundido; reparación no rentable"),
    (10, EstadoPlanta.RETIRADA, "Sin demanda; almacenada en bodega"),
]


def main() -> int:
    setup_logging(logging.INFO)
    db = DatabaseManager(get_database_path())
    db.initialize_schema(get_resource_path(settings.SCHEMA_RELATIVE_PATH))
    servicio = PlantaService(crear_fabrica_uow(db), ConsecutivoService())

    if servicio.listar(incluir_fuera_de_operacion=True):
        print("La base de datos ya tiene plantas; no se cargaron datos de demostración.")
        return 0

    plantas = []
    for fila in _PLANTAS_DEMO:
        marca, modelo, serie, kva, kw, voltaje, fases, comb, tanque, fecha, valor, horas = fila
        plantas.append(
            servicio.registrar(
                DatosPlanta(
                    marca=marca, modelo=modelo, numero_serie=serie, potencia_kva=kva,
                    potencia_kw=kw, voltaje=voltaje, fases=fases, tipo_combustible=comb,
                    capacidad_tanque_gal=tanque, fecha_adquisicion=fecha,
                    valor_compra=valor, horometro_inicial=horas,
                )
            )
        )

    for posicion, estado, motivo in _EVENTOS_DEMO:
        servicio.cambiar_estado(plantas[posicion].id, estado, motivo=motivo)

    print(f"Se cargaron {len(plantas)} plantas de demostración en {db.db_path}")
    print(f"Números libres: {servicio.numeros_libres()} | Próximo: {servicio.proximo_numero()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
