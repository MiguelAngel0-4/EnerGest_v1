-- =====================================================================
-- Migración 004: clientes, contratos de alquiler e ingresos
-- Ruta: src/infrastructure/database/migrations/004_clientes_alquileres_ingresos.sql
-- Versión resultante del esquema: 4
--
-- Origen: diseño aprobado de la Actividad 4.3 (Ingresos).
-- El contrato es la promesa; el ingreso es el dinero que efectivamente llega.
-- =====================================================================

CREATE TABLE IF NOT EXISTS clientes (
    id        INTEGER PRIMARY KEY,
    nombre    TEXT    NOT NULL CHECK (length(trim(nombre)) > 0),
    documento TEXT    UNIQUE,  -- NIT o cédula
    telefono  TEXT,
    activo    INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
) STRICT;

CREATE TABLE IF NOT EXISTS alquileres (
    id              INTEGER PRIMARY KEY,
    planta_id       INTEGER NOT NULL REFERENCES plantas (id) ON DELETE RESTRICT,
    cliente_id      INTEGER NOT NULL REFERENCES clientes (id) ON DELETE RESTRICT,
    fecha_inicio    TEXT    NOT NULL CHECK (date(fecha_inicio) IS fecha_inicio),
    fecha_fin       TEXT    CHECK (date(fecha_fin) IS fecha_fin),  -- NULL = activo
    modalidad       TEXT    NOT NULL CHECK (modalidad IN ('DIA', 'MES')),
    tarifa          INTEGER NOT NULL CHECK (tarifa > 0),
    valor_liquidado INTEGER CHECK (valor_liquidado IS NULL OR valor_liquidado >= 0),
    observaciones   TEXT,
    CHECK (fecha_fin IS NULL OR fecha_fin >= fecha_inicio),
    -- Cerrado si y solo si está liquidado: nunca un contrato a medias.
    CHECK ((fecha_fin IS NULL) = (valor_liquidado IS NULL))
) STRICT;

-- Una planta no puede tener dos contratos activos al mismo tiempo.
CREATE UNIQUE INDEX IF NOT EXISTS uq_alquileres_activo_por_planta
    ON alquileres (planta_id) WHERE fecha_fin IS NULL;
CREATE INDEX IF NOT EXISTS idx_alquileres_cliente ON alquileres (cliente_id);

CREATE TABLE IF NOT EXISTS ingresos (
    id               INTEGER PRIMARY KEY,
    planta_id        INTEGER NOT NULL REFERENCES plantas (id) ON DELETE RESTRICT,
    tipo             TEXT    NOT NULL CHECK (tipo IN ('ALQUILER', 'VENTA', 'OTRO')),
    alquiler_id      INTEGER REFERENCES alquileres (id) ON DELETE RESTRICT,
    cliente_id       INTEGER REFERENCES clientes (id) ON DELETE RESTRICT,
    fecha            TEXT    NOT NULL CHECK (date(fecha) IS fecha),
    descripcion      TEXT    NOT NULL CHECK (length(trim(descripcion)) > 0),
    numero_documento TEXT,
    valor            INTEGER NOT NULL CHECK (valor > 0),
    anulado          INTEGER NOT NULL DEFAULT 0 CHECK (anulado IN (0, 1)),
    motivo_anulacion TEXT,
    fecha_registro   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    CHECK (anulado = 0 OR length(trim(coalesce(motivo_anulacion, ''))) > 0),
    -- Un ingreso de alquiler siempre pertenece a un contrato.
    CHECK (tipo <> 'ALQUILER' OR alquiler_id IS NOT NULL)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_ingresos_planta_fecha ON ingresos (planta_id, fecha);
CREATE INDEX IF NOT EXISTS idx_ingresos_alquiler ON ingresos (alquiler_id);

-- Liga las lecturas de salida y de regreso con su contrato, sin copiarlas.
ALTER TABLE historial_estados ADD COLUMN alquiler_id INTEGER REFERENCES alquileres (id);
