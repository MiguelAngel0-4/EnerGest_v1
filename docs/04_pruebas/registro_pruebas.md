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

## Ciclo 3 — Ajustes de la validación del MVP 1

| Campo                | Detalle                                          |
| -------------------- | ------------------------------------------------ |
| Fecha                | 2026-10-07                                       |
| Versión              | 0.3.0 (esquema de base de datos versión 2)       |
| Responsable          | [Tu nombre]                                      |
| Tipo de prueba       | Unitarias (70), integración (34) e interfaz (19) |
| Casos ejecutados     | 123                                              |
| Aprobados / Fallidos | 123 / 0                                          |
| Evidencia            | 2026-10-07_v0.3.0_ajustes_validacion.html        |

**Hallazgos de la validación atendidos:**

| ID    | Hallazgo                                              | Tipo                | Solución                                                  | Prueba que lo verifica                             |
| ----- | ----------------------------------------------------- | ------------------- | --------------------------------------------------------- | -------------------------------------------------- |
| HZ-01 | No se podía escribir en kW ni en capacidad del tanque | Defecto (Mayor)     | Componente `CampoNumerico` en todos los campos numéricos  | `test_regresion_se_puede_escribir_en_kw_y_tanque`  |
| HZ-02 | Faltaban filtros y datos del aceite en la ficha       | Requerimiento nuevo | Migración 002 y sección "Mantenimiento: filtros y aceite" | `test_consumibles_se_guardan_y_recuperan_intactos` |
| HZ-03 | Pedir la lectura del horómetro al alquilar            | Requerimiento nuevo | Lectura obligatoria al alquilar y opcional al regresar    | `test_alquilar_sin_lectura_es_rechazado`           |
| HZ-04 | Retirar el combustible Gas y sugerir 110/220 V        | Cambio solicitado   | Gas solo como dato histórico                              | `test_registrar_con_gas_es_rechazado`              |

**Observaciones:** durante el ciclo se detectó una edición manual de `schema.sql` (versión 1 congelada, ver ADR-002). La prueba `test_planta_historica_con_gas_se_conserva` la detectó, y el archivo se restauró a su versión original.

## Ciclo 4 — Hoja de vida técnica en PDF (Actividad 3)

| Campo                | Detalle                                          |
| -------------------- | ------------------------------------------------ |
| Fecha                | 2026-10-08                                       |
| Versión              | 0.4.0 (esquema de base de datos versión 2)       |
| Responsable          | [Tu nombre]                                      |
| Tipo de prueba       | Unitarias (78), integración (45) e interfaz (24) |
| Casos ejecutados     | 147                                              |
| Aprobados / Fallidos | 147 / 0                                          |
| Evidencia            | 2026-10-08_v0.4.0_hoja_de_vida_pdf.html          |

**Alcance:** contenido de la hoja de vida, PDF real leído con pypdf
(datos, "No registrado", numeración de páginas), historiales largos en
varias páginas, caracteres especiales, logo válido y dañado, destino
ocupado sin archivos huérfanos, datos de la empresa en JSON (archivo
dañado o ausente) y flujo completo del botón PDF.

**Revisión visual:** se generaron hojas de una planta activa y de una
vendida, y se convirtieron en imagen para revisarlas. Se corrigieron 4
detalles: firmas partidas entre páginas, horómetro duplicado, hueco sin
logo y número liberado que parecía vigente.
