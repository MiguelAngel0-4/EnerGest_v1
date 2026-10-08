"""
Repositorio SQLite de plantas eléctricas.

Ruta: src/infrastructure/repositories/sqlite_planta_repository.py

Cumple el contrato IPlantaRepository. Recibe una conexión ya abierta
por la Unidad de Trabajo: NUNCA abre, confirma ni cierra conexiones
por su cuenta, porque eso rompería la atomicidad de la operación.

Todas las consultas usan parámetros (:nombre o ?), jamás concatenación
de valores del usuario: así se evita la inyección SQL.
"""

import sqlite3
from typing import Any, Final

from src.business.models.estado_planta import EstadoPlanta
from src.business.models.planta import DatosPlanta, Planta, TipoAceite, TipoCombustible
from src.infrastructure.repositories.conversiones import (
    escapar_like,
    fecha_a_texto,
    texto_a_fecha,
    texto_a_fecha_hora,
)

# Columnas que corresponden a DatosPlanta. Son constantes del código
# (no vienen del usuario), por eso es seguro usarlas para armar el SQL.
_COLUMNAS_DATOS: Final[tuple[str, ...]] = (
    "marca",
    "modelo",
    "numero_serie",
    "potencia_kva",
    "potencia_kw",
    "voltaje",
    "fases",
    "tipo_combustible",
    "capacidad_tanque_gal",
    "fecha_adquisicion",
    "valor_compra",
    "horometro_inicial",
    "observaciones",
    "filtro_aceite",
    "filtro_combustible",
    "filtro_agua",
    "filtro_aire",
    "cantidad_aceite_gal",
    "tipo_aceite",
)

# Consulta base: todas las columnas + el horómetro actual CALCULADO (no se guarda
# duplicado). Es el mayor valor entre el horómetro inicial, las lecturas de los
# cambios de estado (alquileres) y las de los mantenimientos NO anulados.
# MAX(a, b, c) con varios argumentos es el máximo escalar de SQLite.
_SQL_SELECT: Final[str] = """
    SELECT p.*,
           MAX(p.horometro_inicial,
               COALESCE((SELECT MAX(h.horometro) FROM historial_estados h
                         WHERE h.planta_id = p.id), 0),
               COALESCE((SELECT MAX(m.horometro) FROM mantenimientos m
                         WHERE m.planta_id = p.id AND m.anulado = 0), 0)) AS horometro_actual
    FROM plantas p
"""

_SQL_INSERTAR: Final[str] = (
    "INSERT INTO plantas (numero_consecutivo, estado, "
    + ", ".join(_COLUMNAS_DATOS)
    + ") VALUES (:numero_consecutivo, :estado, "
    + ", ".join(f":{c}" for c in _COLUMNAS_DATOS)
    + ")"
)

_SQL_ACTUALIZAR_DATOS: Final[str] = (
    "UPDATE plantas SET "
    + ", ".join(f"{c} = :{c}" for c in _COLUMNAS_DATOS)
    + " WHERE id = :id"
)


class SqlitePlantaRepository:
    """Acceso a la tabla plantas."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def insertar(self, datos: DatosPlanta, numero: int, estado: EstadoPlanta) -> int:
        parametros = _datos_a_parametros(datos)
        parametros["numero_consecutivo"] = numero
        parametros["estado"] = estado.value
        cursor = self._conn.execute(_SQL_INSERTAR, parametros)
        return int(cursor.lastrowid)  # type: ignore[arg-type]

    def actualizar_datos(self, planta_id: int, datos: DatosPlanta) -> None:
        parametros = _datos_a_parametros(datos)
        parametros["id"] = planta_id
        self._conn.execute(_SQL_ACTUALIZAR_DATOS, parametros)

    def actualizar_estado(
        self, planta_id: int, estado: EstadoPlanta, numero: int | None
    ) -> None:
        # Estado y número en UNA sentencia: el CHECK de la tabla exige que
        # siempre sean coherentes, incluso entre sentencias.
        self._conn.execute(
            "UPDATE plantas SET estado = ?, numero_consecutivo = ? WHERE id = ?",
            (estado.value, numero, planta_id),
        )

    def obtener(self, planta_id: int) -> Planta | None:
        fila = self._conn.execute(_SQL_SELECT + " WHERE p.id = ?", (planta_id,)).fetchone()
        return _fila_a_planta(fila) if fila is not None else None

    def listar(
        self, estados: set[EstadoPlanta] | None = None, texto: str | None = None
    ) -> list[Planta]:
        condiciones: list[str] = []
        parametros: list[Any] = []

        if estados is not None:
            if not estados:
                return []
            marcadores = ", ".join("?" for _ in estados)
            condiciones.append(f"p.estado IN ({marcadores})")
            parametros.extend(sorted(e.value for e in estados))

        if texto:
            patron = f"%{escapar_like(texto)}%"
            condiciones.append(
                "(p.marca LIKE ? ESCAPE '\\' OR p.modelo LIKE ? ESCAPE '\\' "
                "OR p.numero_serie LIKE ? ESCAPE '\\')"
            )
            parametros.extend([patron, patron, patron])

        sql = _SQL_SELECT
        if condiciones:
            sql += " WHERE " + " AND ".join(condiciones)
        # Primero las plantas con número (en orden), al final las que no tienen.
        sql += " ORDER BY p.numero_consecutivo IS NULL, p.numero_consecutivo, p.id"

        return [_fila_a_planta(f) for f in self._conn.execute(sql, parametros).fetchall()]

    def existe_numero_serie(self, serie: str, excluir_id: int | None = None) -> bool:
        # COLLATE NOCASE: "abc-123" y "ABC-123" se consideran el mismo serial.
        fila = self._conn.execute(
            "SELECT 1 FROM plantas WHERE numero_serie = ? COLLATE NOCASE "
            "AND (? IS NULL OR id <> ?) LIMIT 1",
            (serie, excluir_id, excluir_id),
        ).fetchone()
        return fila is not None


def _datos_a_parametros(datos: DatosPlanta) -> dict[str, Any]:
    """Convierte DatosPlanta en el diccionario de parámetros para SQLite."""
    return {
        "marca": datos.marca,
        "modelo": datos.modelo,
        "numero_serie": datos.numero_serie,
        "potencia_kva": datos.potencia_kva,
        "potencia_kw": datos.potencia_kw,
        "voltaje": datos.voltaje,
        "fases": datos.fases,
        "tipo_combustible": datos.tipo_combustible.value if datos.tipo_combustible else None,
        "capacidad_tanque_gal": datos.capacidad_tanque_gal,
        "fecha_adquisicion": fecha_a_texto(datos.fecha_adquisicion),
        "valor_compra": datos.valor_compra,
        "horometro_inicial": datos.horometro_inicial,
        "observaciones": datos.observaciones,
        "filtro_aceite": datos.filtro_aceite,
        "filtro_combustible": datos.filtro_combustible,
        "filtro_agua": datos.filtro_agua,
        "filtro_aire": datos.filtro_aire,
        "cantidad_aceite_gal": datos.cantidad_aceite_gal,
        "tipo_aceite": datos.tipo_aceite.value if datos.tipo_aceite else None,
    }


def _fila_a_planta(fila: sqlite3.Row) -> Planta:
    """Convierte una fila de la tabla plantas en un objeto Planta."""
    combustible = fila["tipo_combustible"]
    aceite = fila["tipo_aceite"]
    datos = DatosPlanta(
        marca=fila["marca"],
        potencia_kva=fila["potencia_kva"],
        modelo=fila["modelo"],
        numero_serie=fila["numero_serie"],
        potencia_kw=fila["potencia_kw"],
        voltaje=fila["voltaje"],
        fases=fila["fases"],
        tipo_combustible=TipoCombustible(combustible) if combustible else None,
        capacidad_tanque_gal=fila["capacidad_tanque_gal"],
        fecha_adquisicion=texto_a_fecha(fila["fecha_adquisicion"]),
        valor_compra=fila["valor_compra"],
        horometro_inicial=fila["horometro_inicial"],
        observaciones=fila["observaciones"],
        filtro_aceite=fila["filtro_aceite"],
        filtro_combustible=fila["filtro_combustible"],
        filtro_agua=fila["filtro_agua"],
        filtro_aire=fila["filtro_aire"],
        cantidad_aceite_gal=fila["cantidad_aceite_gal"],
        tipo_aceite=TipoAceite(aceite) if aceite else None,
    )
    return Planta(
        id=fila["id"],
        numero_consecutivo=fila["numero_consecutivo"],
        estado=EstadoPlanta(fila["estado"]),
        datos=datos,
        fecha_registro=texto_a_fecha_hora(fila["fecha_registro"]),
        horometro_actual=int(fila["horometro_actual"]),
    )
