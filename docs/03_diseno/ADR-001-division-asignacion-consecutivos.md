# ADR-001: División de la asignación de consecutivos en dos pasos

| Campo            | Detalle                              |
| ---------------- | ------------------------------------ |
| Estado           | Aceptada                             |
| Fecha            | 2026-10-01                           |
| Autor            | [Miguel Angel Fernandez]             |
| Módulo           | Plantas y consecutivos (Actividad 2) |
| Versión afectada | 0.1.0                                |

## Contexto

En el diseño de clases aprobado, el servicio de consecutivos tenía un único método para asignar el número a una planta:

```python
def asignar(self, uow: IUnidadDeTrabajo, planta_id: int, fecha: date) -> int
```

Al implementarlo surgió un conflicto entre dos restricciones del esquema de base de datos, ambas necesarias:

1. **CHECK de la tabla `plantas`:** una planta en estado de operación (DISPONIBLE, ALQUILADA, EN*MANTENIMIENTO) debe tener `numero_consecutivo` distinto de NULL. Por lo tanto, la planta debe \_nacer* con su número.
2. **Llave foránea de `historial_consecutivos`:** el registro del historial apunta a `plantas.id`, así que la planta debe _existir_ antes de registrar su número en el historial.

Para la asignación inicial, el método `asignar` necesitaba el `planta_id`, que solo existe después de insertar la planta. Pero la planta no podía insertarse sin conocer antes su número. Un solo método no podía cumplir ambas condiciones.

## Decisión

Se divide la operación en métodos con responsabilidades separadas: uno que **calcula** el número sin escribir nada y otro que lo **registra** en el historial.

```python
# Calculan el número (solo consultan, no escriben)
def proponer_para_nueva(self, uow: IUnidadDeTrabajo) -> int
def proponer_para_reactivacion(self, uow: IUnidadDeTrabajo, planta_id: int) -> int

# Registra la asignación en el historial (escribe)
def registrar_asignacion(self, uow: IUnidadDeTrabajo, planta_id: int,
                         numero: int, fecha: date) -> None
```

`PlantaService.registrar()` ejecuta los pasos en este orden obligatorio, dentro de una misma unidad de trabajo (transacción):

1. **Calcular** el número con `proponer_para_nueva()`.
2. **Crear** la planta con ese número, cumpliendo el CHECK.
3. **Registrar** la asignación en el historial, cumpliendo la llave foránea.

Si cualquier paso falla, la unidad de trabajo deshace todo (ROLLBACK).

## Alternativas consideradas

| Alternativa                                                     | Motivo del rechazo                                                                                              |
| --------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Insertar la planta sin número y asignarlo después con un UPDATE | Viola el CHECK de coherencia estado-número. Relajar el CHECK eliminaría una defensa en profundidad del esquema. |
| Registrar el historial antes de crear la planta                 | El `planta_id` no se conoce antes del INSERT, y la llave foránea lo rechazaría.                                 |
| Un método del repositorio que haga las tres operaciones juntas  | Movería la regla "menor número libre" a la capa de infraestructura, lo que viola la separación de capas.        |

## Consecuencias

**Positivas:**

- Se respetan simultáneamente el CHECK y la llave foránea, sin debilitar el esquema.
- La regla de negocio (menor número libre y prioridad del número anterior al reactivar) permanece en la capa de lógica.
- Los métodos `proponer_*` solo consultan. La interfaz podrá usarlos para mostrar, antes de guardar, un aviso como "Esta planta recibirá el número PE-004".

**Negativas y mitigación:**

- Quien use el servicio debe respetar el orden calcular → crear → registrar. Si un desarrollador futuro omitiera `registrar_asignacion()`, el historial quedaría incompleto.
- **Mitigación:** solo `PlantaService` invoca estos métodos. Además, las pruebas automatizadas verifican la consistencia del historial y los índices únicos parciales de `historial_consecutivos` impiden registros abiertos duplicados.

## Trazabilidad

| Elemento                          | Referencia                                                                                                                                                                                                                                                 |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Archivos afectados                | `src/business/services/consecutivo_service.py`, `src/business/services/planta_service.py`                                                                                                                                                                  |
| Pruebas que verifican la decisión | `test_registrar_crea_historiales`, `test_vender_libera_numero_y_se_reutiliza`, `test_reactivar_recupera_su_numero_si_esta_libre`, `test_reactivar_recibe_menor_libre_si_su_numero_fue_tomado`, `test_error_a_mitad_de_operacion_no_deja_cambios_parciales` |
| Commit de implementación          | `feat: capa de negocio de plantas y consecutivos` (rama `feature/plantas-consecutivos`)                                                                                                                                                                    |
