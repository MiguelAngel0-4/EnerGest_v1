# Registro de Pruebas

## Ciclo 1 — Base técnica de datos

| Campo                | Detalle                              |
| -------------------- | ------------------------------------ |
| Fecha                | 2026-09-30                           |
| Versión              | 0.1.0                                |
| Responsable          | [Miguel Angel Fernandez]             |
| Tipo de prueba       | Integración (capa de acceso a datos) |
| Ambiente             | Windows, Python 3.x, SQLite local    |
| Casos ejecutados     | 12                                   |
| Aprobados / Fallidos | 12 / 0                               |
| Evidencia            | 2026-09-30_v0.1.0_base_tecnica.html  |

**Alcance:** creación del esquema, llaves foráneas, atomicidad
(rollback), reglas CHECK de consecutivos, validación de fechas,
gastos sin factura, facturas únicas por proveedor y tablas STRICT.

**Observaciones:** ninguna.

## Ciclo 2 — Modulo de plantas

| Campo                | Detalle                                                                                                          |
| -------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Versión              | 0.2.0                                                                                                            |
| Tipo de prueba       | Unitarias (53) e integración (22)                                                                                |
| Casos ejecutados     | 75                                                                                                               |
| Aprobados / Fallidos | 75 / 0                                                                                                           |
| Alcance              | Máquina de estados, consecutivos, validaciones, repositorios SQLite, unidad de trabajo, traductor del formulario |
| Evidencia            | 2026-10-01_v0.2.0_modulo_plantas.html                                                                            |
