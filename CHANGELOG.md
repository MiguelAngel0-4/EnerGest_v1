# Registro de cambios – EnerGest

## [0.7.0] – 2026-10-12

### Agregado

- Contratos de alquiler por día o por mes: al pasar una planta a "Alquilada" se
  registran el cliente, la modalidad, la tarifa y las observaciones.
- Liquidación al devolver una planta: se cobra el tiempo real de uso. Por mes,
  los meses completos de calendario a la tarifa pactada y los días restantes a la
  tarifa mensual ÷ 30. Mínimo un día. El valor sugerido se puede ajustar si se
  negocia un descuento.
- Cobros durante el alquiler (anticipos o cortes mensuales), que se descuentan al
  liquidar, y cobro del saldo pendiente después de la devolución.
- Venta con comprador y precio al pasar una planta a "Vendida".
- Registro de clientes desde los formularios, sin salir del flujo de trabajo.
- Pestaña "Ingresos" en la ficha: contrato activo con lo acumulado a la fecha,
  lista de ingresos y historial de alquileres con horas de uso, valor liquidado,
  cobrado y saldo.
- Al pasar el mouse sobre una planta alquilada, el inventario muestra el cliente
  que la tiene.

### Cambiado

- El cambio de estado a "Alquilada" o "Vendida" exige los datos comerciales;
  al vender, el motivo se completa automáticamente.
- El mensaje que confirma un cambio de estado incluye el contrato, la liquidación
  o el valor de la venta.

### Reglas de negocio

- Una planta no puede tener dos contratos activos.
- Un contrato activo solo se cierra con su liquidación: no con un cambio de estado
  suelto.
- El valor liquidado nunca puede ser menor que lo ya cobrado.
- Las condiciones de un contrato solo se corrigen mientras está activo.
- Los ingresos se anulan con motivo; no se editan ni se borran.
- Los alquileres registrados antes de esta versión no tienen contrato: se
  devuelven sin liquidación y sus cobros se registran como "otro ingreso".

### Base de datos

- Migración 004: clientes, contratos de alquiler, ingresos y vínculo entre las
  lecturas del horómetro y su contrato. Se aplica automáticamente al abrir la
  aplicación, con respaldo previo en `data/respaldos/`.

## [0.6.0] – 2026-10-10

### Agregado

- Pestaña "Mantenimientos" en la ficha de la planta: registro de mantenimientos
  preventivos y correctivos con fecha, lectura del horómetro, técnico y trabajo
  realizado.
- Insumos y mano de obra dentro del mantenimiento, registrados automáticamente
  como gastos de la planta. El botón "Cargar insumos de la ficha técnica" llena
  las líneas con los filtros y el aceite registrados.
- Programación del próximo mantenimiento por fecha, por horas o ambas ("lo que
  ocurra primero"). En los preventivos se sugiere +6 meses y +250 horas.
- Sección "Mantenimientos pendientes" en el inventario, con las plantas vencidas
  en rojo y las próximas en naranja. Un clic abre la ficha en esa pestaña.
- Sección "7. Historial de mantenimientos" en la hoja de vida PDF, con el
  próximo mantenimiento programado.
- Anulación de mantenimientos con motivo: también anula sus gastos, y su lectura
  del horómetro deja de contar.

### Cambiado

- La última lectura del horómetro ahora incluye las tomadas en los mantenimientos.
- Al cerrar la ficha de una planta, el inventario se actualiza (horómetro y alertas).
- Los gastos que nacen de un mantenimiento se identifican en la pestaña Gastos.

### Corregido

- Los botones de opción y las casillas no mostraban su círculo o recuadro.
- Las firmas de la hoja de vida podían quedar solas en una página.

### Reglas de negocio

- El horómetro del mantenimiento es obligatorio y no puede ser menor que la
  última lectura conocida.
- La fecha de un mantenimiento no puede ser anterior a la del último registrado.

### Base de datos

- Migración 003: programación por horas y anulación de mantenimientos. Se aplica
  automáticamente al abrir la aplicación, con respaldo previo en `data/respaldos/`.

## [0.5.0] – 2026-10-09

### Agregado

- Ficha de la planta: ventana con pestañas que reúne su información. Se abre
  con el botón "Ficha" del inventario.
- Pestaña "Gastos" en la ficha: registro de gastos por planta con categoría,
  fecha, descripción, cantidad, unidad y valor, más un resumen de totales por
  categoría y del valor sin soporte.
- Facturas de proveedor que pueden repartirse entre varias plantas, con el saldo
  por asignar siempre visible. Un gasto nunca puede superar ese saldo.
- Registro de proveedores y facturas desde el mismo formulario del gasto.
- Gastos sin factura para compras informales, identificados como "Sin soporte".
- Anulación de gastos con motivo obligatorio: el gasto anulado no se borra,
  queda tachado y se puede consultar con "Mostrar anulados".
- Sugerencias de descripción tomadas de la ficha técnica de la planta
  (referencias de filtros y tipo de aceite).

### Cambiado

- El botón "Historial" del inventario se reemplaza por "Ficha"; el historial de
  estados y de números consecutivos ahora es una pestaña dentro de la ficha.
- Las pestañas que se habilitarán en próximas versiones (Mantenimientos,
  Ingresos y Balance) se muestran atenuadas.

### Reglas de negocio

- No se registran gastos a plantas vendidas o dadas de baja; las retiradas sí
  los admiten.
- Un proveedor no puede repetir un número de factura, y no pueden existir dos
  proveedores con el mismo nombre o NIT.

## [0.4.0] – 2026-10-08

### Agregado

- Hoja de vida técnica en PDF (tamaño carta) con identificación, especificaciones,
  filtros y aceite, operación, historial de estados y de números consecutivos.
- Botón "PDF" en cada fila del inventario, con nombre de archivo sugerido y
  carpeta recordada.
- Datos de la empresa configurables en `data/empresa.json`, con logo opcional (ADR-003).

### Cambiado

- Los botones de acción del inventario se ajustan al ancho de su texto.

## [0.3.0] – 2026-10-07

### Agregado

- Datos de filtros (aceite, combustible/separador, agua y aire), cantidad y tipo de aceite en la ficha de cada planta.
- Lectura del horómetro obligatoria al alquilar y opcional al regresar; el inventario muestra la última lectura.
- Migraciones de base de datos con respaldo automático previo (ADR-002).

### Cambiado

- El combustible Gas ya no se admite en registros nuevos; se conserva en las plantas que ya lo tenían.
- El voltaje sugerido es 110/220 V.

### Corregido

- Los campos numéricos (kW, capacidad del tanque, kVA y horómetro) no permitían escribir directamente.

## [0.2.0] – 2026-10-01

### Agregado

- Inventario de plantas con filtros, búsqueda y panel de números libres.
- Registro, edición, cambio de estado e historial de plantas.
- Asignación automática del menor número consecutivo libre (ADR-001).

## [0.1.0] – 2026-09-30

### Agregado

- Base técnica: conexión a SQLite, esquema de datos, registro de eventos (logs) y rutas portables.
