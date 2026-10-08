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

from src.business.models.comercial import (
    Alquiler,
    Cliente,
    DatosContrato,
    DatosIngreso,
    Ingreso,
    TipoIngreso,
)
from src.business.models.estado_planta import EstadoPlanta
from src.business.models.gasto import (
    CategoriaGasto,
    DatosFactura,
    DatosGasto,
    FacturaProveedor,
    Gasto,
    GastoDetalle,
    Proveedor,
    ResumenGastos,
)
from src.business.models.mantenimiento import DatosMantenimiento, Mantenimiento
from src.business.models.planta import CambioEstado, DatosPlanta, Planta, RegistroConsecutivo

FECHA_REGISTRO_FIJA = datetime(2026, 1, 1, 8, 0, 0)


@dataclass
class AlmacenFake:
    """Estado compartido que simula el contenido de la base de datos."""

    plantas: dict[int, Planta] = field(default_factory=dict)
    consecutivos: list[RegistroConsecutivo] = field(default_factory=list)
    cambios: list[CambioEstado] = field(default_factory=list)
    siguiente_id: int = 1
    # Módulo de gastos
    gastos: dict[int, Gasto] = field(default_factory=dict)
    facturas: dict[int, tuple[DatosFactura, int]] = field(default_factory=dict)  # (datos, id)
    proveedores: dict[int, Proveedor] = field(default_factory=dict)
    categorias: dict[int, CategoriaGasto] = field(
        default_factory=lambda: {
            i: CategoriaGasto(i, nombre)
            for i, nombre in enumerate(
                ["Filtros", "Repuestos", "Aceite y lubricantes", "Mano de obra", "Otros"], 1
            )
        }
    )
    contador: int = 1000  # Ids de gastos, facturas, proveedores y mantenimientos
    # Módulo de mantenimientos: (planta_id, datos, anulado, motivo)
    mantenimientos: dict[int, tuple[int, DatosMantenimiento, bool, str | None]] = field(
        default_factory=dict
    )

    # Módulo comercial
    clientes: dict[int, Cliente] = field(default_factory=dict)
    # alquiler_id -> (planta_id, contrato, fecha_inicio, fecha_fin, valor_liquidado)
    alquileres: dict[int, tuple[int, DatosContrato, date, date | None, int | None]] = field(
        default_factory=dict
    )
    # ingreso_id -> (planta_id, tipo, datos, alquiler_id, cliente_id, anulado, motivo)
    ingresos: dict[int, tuple] = field(default_factory=dict)

    def nuevo_id(self) -> int:
        self.contador += 1
        return self.contador


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
        lecturas += [
            datos.horometro
            for planta_id, datos, anulado, _ in self._a.mantenimientos.values()
            if planta_id == planta.id and not anulado
        ]
        return replace(planta, horometro_actual=max([planta.datos.horometro_inicial, *lecturas]))

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
                if t
                in " ".join(
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


class FakeGastoRepository:
    def __init__(self, almacen: AlmacenFake) -> None:
        self._a = almacen

    def insertar(
        self, planta_id: int, datos: DatosGasto, mantenimiento_id: int | None = None
    ) -> int:
        gasto_id = self._a.nuevo_id()
        self._a.gastos[gasto_id] = Gasto(
            gasto_id, planta_id, datos, mantenimiento_id, False, None, FECHA_REGISTRO_FIJA
        )
        return gasto_id

    def obtener(self, gasto_id: int) -> Gasto | None:
        return self._a.gastos.get(gasto_id)

    def anular(self, gasto_id: int, motivo: str) -> None:
        self._a.gastos[gasto_id] = replace(
            self._a.gastos[gasto_id], anulado=True, motivo_anulacion=motivo
        )

    def anular_por_mantenimiento(self, mantenimiento_id: int, motivo: str) -> None:
        for gasto_id, gasto in list(self._a.gastos.items()):
            if gasto.mantenimiento_id == mantenimiento_id and not gasto.anulado:
                self.anular(gasto_id, motivo)

    def listar_por_planta(
        self, planta_id: int, incluir_anulados: bool = False
    ) -> list[GastoDetalle]:
        gastos = [
            g
            for g in self._a.gastos.values()
            if g.planta_id == planta_id and (incluir_anulados or not g.anulado)
        ]
        gastos.sort(key=lambda g: (g.datos.fecha, g.id), reverse=True)
        detalles = []
        for g in gastos:
            factura = self._a.facturas.get(g.datos.factura_id) if g.datos.factura_id else None
            proveedor = self._a.proveedores[factura[0].proveedor_id].nombre if factura else None
            detalles.append(
                GastoDetalle(
                    g,
                    self._a.categorias[g.datos.categoria_id].nombre,
                    factura[0].numero_factura if factura else None,
                    proveedor,
                    (
                        self._a.mantenimientos[g.mantenimiento_id][1].fecha
                        if g.mantenimiento_id
                        else None
                    ),
                )
            )
        return detalles

    def resumen_por_planta(self, planta_id: int) -> ResumenGastos:
        vigentes = [g for g in self.listar_por_planta(planta_id)]
        por_categoria: dict[str, int] = {}
        for d in vigentes:
            por_categoria[d.categoria] = (
                por_categoria.get(d.categoria, 0) + d.gasto.datos.valor_total
            )
        return ResumenGastos(
            total=sum(d.gasto.datos.valor_total for d in vigentes),
            cantidad=len(vigentes),
            sin_soporte=sum(d.gasto.datos.valor_total for d in vigentes if not d.tiene_soporte),
            por_categoria=tuple(sorted(por_categoria.items(), key=lambda par: (-par[1], par[0]))),
        )


class FakeFacturaRepository:
    def __init__(self, almacen: AlmacenFake) -> None:
        self._a = almacen

    def insertar(self, datos: DatosFactura) -> int:
        factura_id = self._a.nuevo_id()
        self._a.facturas[factura_id] = (datos, factura_id)
        return factura_id

    def obtener(self, factura_id: int) -> FacturaProveedor | None:
        if factura_id not in self._a.facturas:
            return None
        datos, _ = self._a.facturas[factura_id]
        asignado = sum(
            g.datos.valor_total
            for g in self._a.gastos.values()
            if g.datos.factura_id == factura_id and not g.anulado
        )
        nombre = self._a.proveedores[datos.proveedor_id].nombre
        return FacturaProveedor(factura_id, datos, nombre, asignado)

    def existe_numero(self, proveedor_id: int, numero: str) -> bool:
        return any(
            d.proveedor_id == proveedor_id
            and d.numero_factura.strip().casefold() == numero.strip().casefold()
            for d, _ in self._a.facturas.values()
        )

    def listar_con_saldo(self, texto: str | None = None) -> list[FacturaProveedor]:
        facturas = [self.obtener(i) for i in self._a.facturas]
        resultado = [f for f in facturas if f is not None and f.saldo_por_asignar > 0]
        if texto:
            t = texto.casefold()
            resultado = [
                f
                for f in resultado
                if t in f.datos.numero_factura.casefold() or t in f.proveedor_nombre.casefold()
            ]
        return resultado


class FakeProveedorRepository:
    def __init__(self, almacen: AlmacenFake) -> None:
        self._a = almacen

    def insertar(self, nombre: str, nit: str | None, telefono: str | None) -> int:
        proveedor_id = self._a.nuevo_id()
        self._a.proveedores[proveedor_id] = Proveedor(proveedor_id, nombre, nit, telefono)
        return proveedor_id

    def obtener(self, proveedor_id: int) -> Proveedor | None:
        return self._a.proveedores.get(proveedor_id)

    def listar(self) -> list[Proveedor]:
        activos = [p for p in self._a.proveedores.values() if p.activo]
        return sorted(activos, key=lambda p: p.nombre.casefold())

    def existe_nombre(self, nombre: str) -> bool:
        objetivo = nombre.strip().casefold()
        return any(p.nombre.strip().casefold() == objetivo for p in self._a.proveedores.values())

    def existe_nit(self, nit: str) -> bool:
        objetivo = nit.strip().casefold()
        return any(
            (p.nit or "").strip().casefold() == objetivo for p in self._a.proveedores.values()
        )


class FakeCategoriaRepository:
    def __init__(self, almacen: AlmacenFake) -> None:
        self._a = almacen

    def obtener(self, categoria_id: int) -> CategoriaGasto | None:
        return self._a.categorias.get(categoria_id)

    def listar(self) -> list[CategoriaGasto]:
        return [c for c in self._a.categorias.values() if c.activo]


class FakeMantenimientoRepository:
    def __init__(self, almacen: AlmacenFake) -> None:
        self._a = almacen

    def insertar(self, planta_id: int, datos: DatosMantenimiento) -> int:
        mantenimiento_id = self._a.nuevo_id()
        self._a.mantenimientos[mantenimiento_id] = (planta_id, datos, False, None)
        return mantenimiento_id

    def obtener(self, mantenimiento_id: int) -> Mantenimiento | None:
        if mantenimiento_id not in self._a.mantenimientos:
            return None
        planta_id, datos, anulado, motivo = self._a.mantenimientos[mantenimiento_id]
        costo = sum(
            g.datos.valor_total
            for g in self._a.gastos.values()
            if g.mantenimiento_id == mantenimiento_id and not g.anulado
        )
        return Mantenimiento(mantenimiento_id, planta_id, datos, anulado, motivo, costo)

    def anular(self, mantenimiento_id: int, motivo: str) -> None:
        planta_id, datos, _, _ = self._a.mantenimientos[mantenimiento_id]
        self._a.mantenimientos[mantenimiento_id] = (planta_id, datos, True, motivo)

    def listar_por_planta(
        self, planta_id: int, incluir_anulados: bool = False
    ) -> list[Mantenimiento]:
        todos = [self.obtener(i) for i in self._a.mantenimientos]
        lista = [
            m
            for m in todos
            if m is not None and m.planta_id == planta_id and (incluir_anulados or not m.anulado)
        ]
        return sorted(lista, key=lambda m: (m.datos.fecha, m.id), reverse=True)

    def ultimo_vigente(self, planta_id: int) -> Mantenimiento | None:
        vigentes = self.listar_por_planta(planta_id)
        return vigentes[0] if vigentes else None

    def ultimos_por_planta(self) -> dict[int, Mantenimiento]:
        plantas = {planta_id for planta_id, *_ in self._a.mantenimientos.values()}
        ultimos = {p: self.ultimo_vigente(p) for p in plantas}
        return {p: m for p, m in ultimos.items() if m is not None}

    def tecnicos_registrados(self) -> list[str]:
        nombres = {
            datos.tecnico.strip()
            for _, datos, _, _ in self._a.mantenimientos.values()
            if datos.tecnico
        }
        return sorted(nombres, key=str.casefold)


class FakeClienteRepository:
    def __init__(self, almacen: AlmacenFake) -> None:
        self._a = almacen

    def insertar(self, nombre: str, documento: str | None, telefono: str | None) -> int:
        cliente_id = self._a.nuevo_id()
        self._a.clientes[cliente_id] = Cliente(cliente_id, nombre, documento, telefono)
        return cliente_id

    def obtener(self, cliente_id: int) -> Cliente | None:
        return self._a.clientes.get(cliente_id)

    def listar(self) -> list[Cliente]:
        return sorted(
            (c for c in self._a.clientes.values() if c.activo), key=lambda c: c.nombre.casefold()
        )

    def existe_nombre(self, nombre: str) -> bool:
        objetivo = nombre.strip().casefold()
        return any(c.nombre.strip().casefold() == objetivo for c in self._a.clientes.values())

    def existe_documento(self, documento: str) -> bool:
        objetivo = documento.strip().casefold()
        return any(
            (c.documento or "").strip().casefold() == objetivo for c in self._a.clientes.values()
        )


class FakeAlquilerRepository:
    def __init__(self, almacen: AlmacenFake) -> None:
        self._a = almacen

    def insertar(self, planta_id: int, contrato: DatosContrato, fecha_inicio: date) -> int:
        if self.activo_de(planta_id) is not None:  # Igual que el índice único de SQLite
            raise RuntimeError("Ya hay un contrato activo para esta planta")
        alquiler_id = self._a.nuevo_id()
        self._a.alquileres[alquiler_id] = (planta_id, contrato, fecha_inicio, None, None)
        return alquiler_id

    def obtener(self, alquiler_id: int) -> Alquiler | None:
        if alquiler_id not in self._a.alquileres:
            return None
        planta_id, contrato, inicio, fin, liquidado = self._a.alquileres[alquiler_id]
        cobrado = sum(
            datos.valor
            for (_, _, datos, a_id, _, anulado, _) in self._a.ingresos.values()
            if a_id == alquiler_id and not anulado
        )
        lecturas = [
            c.horometro
            for c in self._a.cambios
            if c.alquiler_id == alquiler_id and c.horometro is not None
        ]
        horas = max(lecturas) - min(lecturas) if len(lecturas) >= 2 else None
        return Alquiler(
            alquiler_id,
            planta_id,
            contrato.cliente_id,
            self._a.clientes[contrato.cliente_id].nombre,
            inicio,
            fin,
            contrato.modalidad,
            contrato.tarifa,
            liquidado,
            contrato.observaciones,
            cobrado,
            horas,
        )

    def activo_de(self, planta_id: int) -> Alquiler | None:
        for alquiler_id, (p_id, _, _, fin, _) in self._a.alquileres.items():
            if p_id == planta_id and fin is None:
                return self.obtener(alquiler_id)
        return None

    def cerrar(self, alquiler_id: int, fecha_fin: date, valor_liquidado: int) -> None:
        planta_id, contrato, inicio, _, _ = self._a.alquileres[alquiler_id]
        self._a.alquileres[alquiler_id] = (planta_id, contrato, inicio, fecha_fin, valor_liquidado)

    def actualizar_condiciones(self, alquiler_id: int, contrato: DatosContrato) -> None:
        planta_id, _, inicio, fin, liquidado = self._a.alquileres[alquiler_id]
        self._a.alquileres[alquiler_id] = (planta_id, contrato, inicio, fin, liquidado)

    def listar_por_planta(self, planta_id: int) -> list[Alquiler]:
        lista = [self.obtener(i) for i, v in self._a.alquileres.items() if v[0] == planta_id]
        return sorted((a for a in lista if a), key=lambda a: (a.fecha_inicio, a.id), reverse=True)

    def clientes_actuales(self) -> dict[int, str]:
        actuales = {}
        for alquiler_id, (planta_id, _, _, fin, _) in self._a.alquileres.items():
            if fin is None:
                actuales[planta_id] = self.obtener(alquiler_id).cliente_nombre  # type: ignore[union-attr]
        return actuales


class FakeIngresoRepository:
    def __init__(self, almacen: AlmacenFake) -> None:
        self._a = almacen

    def insertar(
        self,
        planta_id: int,
        tipo: TipoIngreso,
        datos: DatosIngreso,
        alquiler_id: int | None = None,
        cliente_id: int | None = None,
    ) -> int:
        ingreso_id = self._a.nuevo_id()
        self._a.ingresos[ingreso_id] = (
            planta_id,
            tipo,
            datos,
            alquiler_id,
            cliente_id,
            False,
            None,
        )
        return ingreso_id

    def obtener(self, ingreso_id: int) -> Ingreso | None:
        if ingreso_id not in self._a.ingresos:
            return None
        planta_id, tipo, datos, alquiler_id, cliente_id, anulado, motivo = self._a.ingresos[
            ingreso_id
        ]
        nombre = self._a.clientes[cliente_id].nombre if cliente_id else None
        return Ingreso(
            ingreso_id, planta_id, tipo, alquiler_id, cliente_id, nombre, datos, anulado, motivo
        )

    def anular(self, ingreso_id: int, motivo: str) -> None:
        valores = list(self._a.ingresos[ingreso_id])
        valores[5], valores[6] = True, motivo
        self._a.ingresos[ingreso_id] = tuple(valores)

    def listar_por_planta(self, planta_id: int, incluir_anulados: bool = False) -> list[Ingreso]:
        lista = [self.obtener(i) for i, v in self._a.ingresos.items() if v[0] == planta_id]
        vigentes = [i for i in lista if i and (incluir_anulados or not i.anulado)]
        return sorted(vigentes, key=lambda i: (i.datos.fecha, i.id), reverse=True)


class FakeUnidadDeTrabajo:
    """Simula la transacción: si hay error, restaura la copia tomada al entrar."""

    def __init__(self, almacen: AlmacenFake) -> None:
        self._almacen = almacen
        self._respaldo: dict[str, object] = {}
        self.plantas = FakePlantaRepository(almacen)
        self.consecutivos = FakeConsecutivoRepository(almacen)
        self.historial_estados = FakeHistorialEstadoRepository(almacen)
        self.gastos = FakeGastoRepository(almacen)
        self.facturas = FakeFacturaRepository(almacen)
        self.proveedores = FakeProveedorRepository(almacen)
        self.categorias = FakeCategoriaRepository(almacen)
        self.mantenimientos = FakeMantenimientoRepository(almacen)
        self.clientes = FakeClienteRepository(almacen)
        self.alquileres = FakeAlquilerRepository(almacen)
        self.ingresos = FakeIngresoRepository(almacen)

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
