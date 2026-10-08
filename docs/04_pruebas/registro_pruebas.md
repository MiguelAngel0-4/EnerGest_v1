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

## Ciclo 6 — Mantenimientos (Actividad 4.2)

| Campo                | Detalle                                                   |
| -------------------- | --------------------------------------------------------- |
| Fecha                | 2026-10-10                                                |
| Versión              | 0.6.0 (esquema de base de datos versión 3, migración 003) |
| Responsable          | [Tu nombre]                                               |
| Tipo de prueba       | Unitarias (110), integración (55) e interfaz (43)         |
| Casos ejecutados     | 208 (34 nuevos en este ciclo)                             |
| Aprobados / Fallidos | 208 / 0                                                   |
| Evidencia            | 2026-10-10_v0.6.0_mantenimientos.html                     |

**Pruebas nuevas por regla de negocio:**

| Regla                                                                  | Prueba que la verifica                                                                                   |
| ---------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Sin mantenimientos a plantas vendidas o dadas de baja; sí a alquiladas | `test_plantas_vendidas_no_admiten_mantenimientos`, `test_planta_alquilada_admite_mantenimiento_en_sitio` |
| Horómetro obligatorio, que nunca retrocede y actualiza la planta       | `test_horometro_no_puede_retroceder`, `test_el_horometro_del_mantenimiento_actualiza_la_planta`          |
| Fechas en orden cronológico                                            | `test_fecha_anterior_al_ultimo_mantenimiento_es_rechazada`                                               |
| Próximo mantenimiento siempre posterior; sugerencia según calendario   | `test_proximo_debe_quedar_despues`, `test_proximo_sugerido_respeta_el_calendario`                        |
| Insumos como gastos ligados, todo o nada                               | `test_registrar_con_insumos_crea_gastos_ligados`, `test_insumos_que_superan_la_factura_no_guardan_nada`  |
| Anulación en cascada (gastos y lectura)                                | `test_anular_anula_sus_gastos_y_su_lectura`                                                              |
| Alertas por fecha y por horas                                          | `test_alertas_por_fecha_y_por_horas`, `test_un_alquiler_puede_vencer_un_mantenimiento_por_horas`         |
| El esquema respalda las reglas                                         | `test_el_esquema_rechaza_un_proximo_menor_que_la_lectura`                                                |

**Migración:** se verificó la migración 003 sobre una base real de la versión
0.5.0 con gastos y un mantenimiento previo: se creó el respaldo automático, el
mantenimiento antiguo se conservó y su lectura pasó a contar en el horómetro actual.

**Hallazgos corregidos durante el ciclo:**

| Hallazgo                                                                                                         | Corrección                                                                                             | Prueba de regresión                                                |
| ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------ |
| Prueba de la versión 0.5.0 que fallaría con el paso de los días (reloj fijo frente al reloj real del formulario) | Los recorridos de interfaz usan el reloj real; se verificó adelantando el reloj 30 días con `faketime` | `test_registrar_y_anular_desde_la_ficha`                           |
| El orden de las alertas comparaba días con horas                                                                 | Orden fijo: vencidas primero y luego por número de planta                                              | `test_alertas_por_fecha_y_por_horas`                               |
| Las firmas del PDF quedaban solas en la página 2                                                                 | Las firmas viajan con la última sección                                                                | `test_las_firmas_nunca_quedan_solas_en_una_pagina`                 |
| El simulador de teclado abortaba con tildes                                                                      | Guarda con mensaje claro                                                                               | `test_el_simulador_de_teclado_rechaza_tildes_con_un_mensaje_claro` |

**Revisión visual:** se corrigieron la altura del formulario de mantenimiento
(808 px a 697 px), el título recortado del panel de alertas y los indicadores
de los botones de opción y casillas (sin círculo ni recuadro desde la versión 0.5.0).

## Ciclo 7 — Ingresos: alquileres, ventas y cobros (Actividad 4.3)

| Campo                | Detalle                                                   |
| -------------------- | --------------------------------------------------------- |
| Fecha                | 2026-10-12                                                |
| Versión              | 0.7.0 (esquema de base de datos versión 4, migración 004) |
| Responsable          | [Tu nombre]                                               |
| Tipo de prueba       | Unitarias (135), integración (59) e interfaz (50)         |
| Casos ejecutados     | 244 (36 nuevos en este ciclo)                             |
| Aprobados / Fallidos | 244 / 0                                                   |
| Evidencia            | 2026-10-12_v0.7.0_ingresos.html                           |

**Pruebas de la fórmula de liquidación aprobada por la empresa:**

| Caso                                      | Resultado esperado            | Prueba                                                                       |
| ----------------------------------------- | ----------------------------- | ---------------------------------------------------------------------------- |
| 01/10 → 11/11, tarifa mensual $ 3.000.000 | 1 mes y 10 días = $ 4.000.000 | `test_ejemplos_aprobados_por_mes`                                            |
| 01/10 → 21/10                             | 20 días = $ 2.000.000         | `test_ejemplos_aprobados_por_mes`                                            |
| 01/10 → 01/12                             | 2 meses exactos = $ 6.000.000 | `test_ejemplos_aprobados_por_mes`                                            |
| 31/01 → 28/02 (fin de mes)                | 1 mes = $ 3.000.000           | `test_ejemplos_aprobados_por_mes`                                            |
| Entrega y devolución el mismo día         | Mínimo 1 día                  | `test_ejemplos_aprobados_por_mes`, `test_por_dia_cuenta_dias_con_minimo_uno` |
| Fracción de peso                          | Redondeo al peso más cercano  | `test_redondeo_al_peso_mas_cercano`                                          |

**Pruebas nuevas por regla de negocio:**

| Regla                                                          | Prueba que la verifica                                                                        |
| -------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| Alquilar = contrato + estado + lectura ligada, todo o nada     | `test_alquilar_crea_contrato_y_cambia_el_estado`, `test_un_alquiler_fallido_no_deja_contrato` |
| Cobros parciales que se descuentan al cerrar                   | `test_devolver_por_mes_proporcional_con_anticipo`                                             |
| Descuento negociado, nunca por debajo de lo cobrado            | `test_descuento_negociado_sin_bajar_de_lo_cobrado`                                            |
| Saldo pendiente cobrable después, sin excederlo                | `test_saldo_pendiente_se_cobra_despues_sin_excederlo`                                         |
| Un daño durante el alquiler cierra el contrato                 | `test_dano_durante_el_alquiler_cierra_el_contrato`                                            |
| Alquileres anteriores a la 0.7.0 sin contrato                  | `test_alquiler_antiguo_sin_contrato_solo_cambia_el_estado`                                    |
| Un contrato activo no se cierra con un cambio de estado suelto | `test_contrato_activo_no_se_salta_con_un_cambio_de_estado_suelto`                             |
| Venta = ingreso + estado                                       | `test_vender_registra_el_ingreso_y_el_estado`, `test_venta_sin_precio_no_cambia_nada`         |
| Nunca dos contratos activos (defensa en profundidad)           | `test_el_esquema_impide_dos_contratos_activos`                                                |

**Recorridos de interfaz:** alquilar y devolver desde el inventario (con
liquidación, cobro y horas de uso), y cobrar y anular desde la ficha.

**Migración:** se verificó la migración 004 sobre una base real de la versión
0.6.0 con plantas alquiladas sin contrato: se creó el respaldo automático y esas
plantas se devuelven sin liquidación, conservando sus datos históricos.

**Hallazgos corregidos durante el ciclo:**

| Hallazgo                                                                                                                    | Corrección                                                          | Prueba de regresión                               |
| --------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------- |
| El mensaje de error del diálogo de estado se ocultaba solo (el reformateo automático del horómetro disparaba `textChanged`) | Se usa `textEdited`, que solo reacciona a lo que escribe el usuario | `test_alquilar_sin_cliente_ni_tarifa_no_se_envia` |
| El mensaje final de un cambio de estado no informaba el resultado comercial                                                 | Incluye contrato, liquidación con saldo o valor de la venta         | Revisión del recorrido completo                   |
