-- =====================================================================
-- Migración 002: filtros y aceite en plantas; horómetro en cambios de estado
-- Ruta: src/infrastructure/database/migrations/002_consumibles_y_horometro.sql
-- Versión resultante del esquema: 2
--
-- Origen: observaciones de la validación del MVP 1.
-- Todas las columnas nuevas admiten NULL: las plantas registradas antes de
-- esta versión no tenían estos datos, y eso no debe invalidarlas.
-- =====================================================================

-- Consumibles de mantenimiento (datos para la hoja de vida)
ALTER TABLE plantas ADD COLUMN filtro_aceite TEXT;
ALTER TABLE plantas ADD COLUMN filtro_combustible TEXT;
ALTER TABLE plantas ADD COLUMN filtro_agua TEXT;
ALTER TABLE plantas ADD COLUMN filtro_aire TEXT;
ALTER TABLE plantas ADD COLUMN cantidad_aceite_gal REAL
    CHECK (cantidad_aceite_gal IS NULL OR cantidad_aceite_gal > 0);
ALTER TABLE plantas ADD COLUMN tipo_aceite TEXT
    CHECK (tipo_aceite IS NULL OR tipo_aceite IN ('SAE_15W40', 'SAE_25W60'));

-- Lectura del horómetro en el momento de un cambio de estado.
-- Obligatoria al pasar a ALQUILADA (regla del servicio, no del esquema:
-- los alquileres registrados antes de esta versión no tienen lectura).
ALTER TABLE historial_estados ADD COLUMN horometro INTEGER
    CHECK (horometro IS NULL OR horometro >= 0);
