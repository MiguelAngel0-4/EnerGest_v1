# Registro de cambios – EnerGest

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