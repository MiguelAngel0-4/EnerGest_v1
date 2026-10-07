"""
Implementaciones en memoria de los contratos de repositorio.

Ruta: tests/unit/fakes.py

Cumplen los mismos Protocol que los repositorios SQLite, pero guardan
todo en diccionarios y listas. Permiten probar la lógica de negocio en
milisegundos y sin base de datos: son el "simulador de vuelo" del servicio.
"""

import copy
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from types import TracebackType
from typing import Self

from src.business.models.estado_planta import EstadoPlanta
from src.business.models.planta import CambioEstado, DatosPlanta, Planta, RegistroConsecutivo

FECHA_REGISTRO_FIJA = datetime(2026, 1, 1, 8, 0, 0)


@dataclass
class AlmacenFake:
    """Estado compartido que simula el contenido de la base de datos."""

    plantas: dict[int, Planta] = field(default_factory=dict)
    consecutivos: list[RegistroConsecutivo] = field(default_factory=list)
    cambios: list[CambioEstado] = field(default_factory=list)
    siguiente_id: int = 1


class FakePlantaRepository:
    def __init__(self, almacen: AlmacenFake) -> None:
        self._a = almacen

    def insertar(self, datos: DatosPlanta, numero: int, estado: EstadoPlanta) -> int:
        planta_id = self._a.siguiente_id
        self._a.siguiente_id += 1
        self._a.plantas[planta_id] = Planta(
            planta_id, numero, estado, datos, FECHA_REGISTRO_FIJA, datos.horometro_inicial
        )
        return planta_id

    def actualizar_datos(self, planta_id: int, datos: DatosPlanta) -> None:
        self._a.plantas[planta_id] = replace(self._a.plantas[planta_id], datos=datos)

    def actualizar_estado(self, planta_id: int, estado: EstadoPlanta, numero: int | None) -> None:
        self._a.plantas[planta_id] = replace(
            self._a.plantas[planta_id], estado=estado, numero_consecutivo=numero
        )

    def obtener(self, planta_id: int) -> Planta | None:
        planta = self._a.plantas.get(planta_id)
        return self._con_horometro_actual(planta) if planta else None

    def _con_horometro_actual(self, planta: Planta) -> Planta:
        """Calcula el horómetro actual igual que la consulta SQL del repositorio real."""
        lecturas = [
            c.horometro
            for c in self._a.cambios
            if c.planta_id == planta.id and c.horometro is not None
        ]
        return replace(
            planta, horometro_actual=max([planta.datos.horometro_inicial, *lecturas])
        )

    def listar(
        self, estados: set[EstadoPlanta] | None = None, texto: str | None = None
    ) -> list[Planta]:
        resultado = [self._con_horometro_actual(p) for p in self._a.plantas.values()]
        if estados is not None:
            resultado = [p for p in resultado if p.estado in estados]
        if texto:
            t = texto.lower()
            resultado = [
                p
                for p in resultado
                if t in " ".join(
                    filter(None, [p.datos.marca, p.datos.modelo, p.datos.numero_serie])
                ).lower()
            ]
        return resultado

    def existe_numero_serie(self, serie: str, excluir_id: int | None = None) -> bool:
        return any(
            p.datos.numero_serie == serie and p.id != excluir_id for p in self._a.plantas.values()
        )


class FakeConsecutivoRepository:
    def __init__(self, almacen: AlmacenFake) -> None:
        self._a = almacen

    def numeros_en_uso(self) -> set[int]:
        return {
            p.numero_consecutivo
            for p in self._a.plantas.values()
            if p.numero_consecutivo is not None
        }

    def abrir_registro(self, planta_id: int, numero: int, fecha: date) -> None:
        self._a.consecutivos.append(RegistroConsecutivo(planta_id, numero, fecha))

    def cerrar_registro(self, planta_id: int, fecha: date, motivo: str) -> None:
        for i, reg in enumerate(self._a.consecutivos):
            if reg.planta_id == planta_id and reg.vigente:
                self._a.consecutivos[i] = replace(
                    reg, fecha_liberacion=fecha, motivo_liberacion=motivo
                )

    def ultimo_numero_de(self, planta_id: int) -> int | None:
        registros = self.historial_de_planta(planta_id)
        return registros[-1].numero if registros else None

    def historial_de_planta(self, planta_id: int) -> list[RegistroConsecutivo]:
        return [r for r in self._a.consecutivos if r.planta_id == planta_id]

    def historial_de_numero(self, numero: int) -> list[RegistroConsecutivo]:
        return [r for r in self._a.consecutivos if r.numero == numero]


class FakeHistorialEstadoRepository:
    def __init__(self, almacen: AlmacenFake) -> None:
        self._a = almacen

    def registrar(self, cambio: CambioEstado) -> None:
        self._a.cambios.append(cambio)

    def listar_por_planta(self, planta_id: int) -> list[CambioEstado]:
        return [c for c in self._a.cambios if c.planta_id == planta_id]


class FakeUnidadDeTrabajo:
    """Simula la transacción: si hay error, restaura la copia tomada al entrar."""

    def __init__(self, almacen: AlmacenFake) -> None:
        self._almacen = almacen
        self._respaldo: dict[str, object] = {}
        self.plantas = FakePlantaRepository(almacen)
        self.consecutivos = FakeConsecutivoRepository(almacen)
        self.historial_estados = FakeHistorialEstadoRepository(almacen)

    def __enter__(self) -> Self:
        self._respaldo = copy.deepcopy(vars(self._almacen))
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            vars(self._almacen).update(self._respaldo)  # "ROLLBACK"
