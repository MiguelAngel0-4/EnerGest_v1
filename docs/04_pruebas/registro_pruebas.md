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

## Ciclo 5 — Gastos por planta (Actividad 4.1)

| Campo                | Detalle                                                   |
| -------------------- | --------------------------------------------------------- |
| Fecha                | 2026-10-09                                                |
| Versión              | 0.5.0 (esquema de base de datos versión 2, sin migración) |
| Responsable          | [Tu nombre]                                               |
| Tipo de prueba       | Unitarias (91), integración (51) e interfaz (32)          |
| Casos ejecutados     | 174 (27 nuevos en este ciclo)                             |
| Aprobados / Fallidos | 174 / 0                                                   |
| Evidencia            | 2026-10-09_v0.5.0_gastos.html                             |

**Pruebas nuevas por regla de negocio:**

| Regla                                                    | Prueba que la verifica                                                                              |
| -------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Gasto por planta; factura opcional ("Sin soporte")       | `test_gasto_sin_factura_queda_sin_soporte`                                                          |
| Factura repartida entre plantas sin superar su total     | `test_factura_repartida_entre_dos_plantas`, `test_no_se_puede_superar_el_saldo_de_la_factura`       |
| Anular un gasto devuelve su valor al saldo de la factura | `test_anular_un_gasto_devuelve_su_valor_al_saldo`                                                   |
| Factura única por proveedor (sin distinguir mayúsculas)  | `test_factura_repetida_para_el_mismo_proveedor`, `test_factura_duplicada_sin_distinguir_mayusculas` |
| Proveedor único por nombre y NIT                         | `test_proveedor_repetido_por_nombre_o_nit`                                                          |
| Sin gastos a plantas vendidas o dadas de baja            | `test_no_se_registran_gastos_a_plantas_vendidas`, `test_planta_dada_de_baja_rechaza_gastos`         |
| Anular en lugar de borrar, con motivo obligatorio        | `test_anular_exige_motivo_y_no_se_repite`, `test_anulados_se_ocultan_pero_no_se_pierden`            |
| El esquema respalda las reglas (defensa en profundidad)  | `test_el_esquema_respalda_las_reglas`                                                               |

**Pruebas de interfaz:** escritura real en los campos de cantidad y valor,
selección obligatoria de factura cuando se marca "Con factura", saldo visible
de la factura elegida, sugerencias de descripción según la categoría, gasto
anulado tachado y un recorrido completo por la ficha: registrar un gasto con la
descripción sugerida desde la ficha técnica, verificar el resumen y anularlo.

**Revisión visual:** se recorrió la ficha completa con un proveedor, una factura
y dos gastos (uno con factura y otro sin ella). Se corrigieron 3 detalles: las
pestañas deshabilitadas se veían iguales a las activas, el texto de la factura
se cortaba en la lista y los botones de opción tenían un fondo gris en el diálogo.

**Observaciones:** el archivo `historial_planta_dialog.py` se eliminó con
`git rm`, porque su contenido pasó a la pestaña Historial de la ficha. La entrega
G1 se copió inicialmente en `develop` antes de crear la rama `feature/gastos`;
se corrigió moviendo los cambios a la rama antes del commit.
