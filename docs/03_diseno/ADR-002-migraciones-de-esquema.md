# ADR-002: Migraciones versionadas del esquema con respaldo automático

| Campo | Detalle |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-10-07 |
| Autor | [Tu nombre] |
| Módulo | Base técnica de datos (afecta a todo el sistema) |
| Versión afectada | 0.3.0 (esquema versión 2) |

## Contexto

La validación del MVP 1 pidió agregar a cada planta los datos de filtros y aceite, y registrar la lectura del horómetro al alquilar. Esto exige nuevas columnas en la base de datos.

Hasta la versión 0.2.0, `schema.sql` solo sabía crear una base desde cero. En los equipos de la empresa ya existe una base con información real, que no puede borrarse para actualizar el programa.

## Decisión

1. `schema.sql` queda **congelado** como versión 1 del esquema y no se modifica nunca más.
2. Cada cambio posterior es un archivo `NNN_descripcion.sql` en `src/infrastructure/database/migrations/`, que lleva la base a la versión `NNN`.
3. `PRAGMA user_version` registra la versión de cada archivo `.db`. Al iniciar, `DatabaseManager.initialize_schema()` aplica en orden las migraciones pendientes.
4. Cada migración se ejecuta en su propia transacción, junto con la actualización de `user_version`: o se aplica completa o no se aplica.
5. Antes de migrar una base con datos, se crea un respaldo automático en `data/respaldos/` con la API de respaldo nativa de SQLite.
6. La aplicación se niega a iniciar si la base es más nueva que el programa, o si existe una migración mayor que `settings.SCHEMA_VERSION`.

## Alternativas consideradas

| Alternativa | Motivo del rechazo |
|---|---|
| Editar `schema.sql` y pedir que se borre la base | Destruye la información real de la empresa |
| Mantener un `schema.sql` actualizado más las migraciones | Dos fuentes de verdad que pueden divergir; una base nueva y una migrada podrían quedar distintas |
| Usar una librería de migraciones (por ejemplo, Alembic) | Exige un ORM o configuración adicional, desproporcionada para SQLite local y un equipo de una persona |

## Consecuencias

**Positivas:** una base nueva y una existente terminan exactamente iguales; las actualizaciones no pierden datos; siempre existe un respaldo previo a cada migración; los errores de versión se detectan al iniciar, con un mensaje claro.

**Negativas y mitigación:** cada cambio de esquema exige crear un archivo de migración y actualizar `SCHEMA_VERSION`. La prueba `test_schema_version_coincide_con_la_ultima_migracion` y la validación al iniciar detectan el olvido. En la Actividad 5, la carpeta `migrations/` deberá incluirse en el empaquetado del ejecutable.

## Trazabilidad

| Elemento | Referencia |
|---|---|
| Archivos | `src/infrastructure/database/connection.py`, `src/infrastructure/database/migrations/002_consumibles_y_horometro.sql` |
| Pruebas | `tests/integration/test_migraciones.py` (8 pruebas) |
| Origen | Observaciones de la validación del MVP 1 |
