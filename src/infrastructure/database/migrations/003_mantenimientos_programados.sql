-- =====================================================================
-- Migración 003: programación y anulación de mantenimientos
-- Ruta: src/infrastructure/database/migrations/003_mantenimientos_programados.sql
-- Versión resultante del esquema: 3
--
-- Origen: diseño aprobado de la Actividad 4.2 (Mantenimientos).
-- =====================================================================

-- Próximo mantenimiento por horas (el "sticker del cambio de aceite").
-- Debe quedar por encima de la lectura del mantenimiento actual.
ALTER TABLE mantenimientos ADD COLUMN proximo_horometro INTEGER
    CHECK (proximo_horometro IS NULL OR proximo_horometro > horometro);

-- Los mantenimientos no se borran: se anulan con motivo, como los gastos.
ALTER TABLE mantenimientos ADD COLUMN anulado INTEGER NOT NULL DEFAULT 0
    CHECK (anulado IN (0, 1));
ALTER TABLE mantenimientos ADD COLUMN motivo_anulacion TEXT
    CHECK (anulado = 0 OR length(trim(coalesce(motivo_anulacion, ''))) > 0);
