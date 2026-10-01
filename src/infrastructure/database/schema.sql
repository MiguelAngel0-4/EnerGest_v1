-- =====================================================================
-- Esquema de base de datos - Gestión de Plantas Eléctricas
-- Ruta: src/infrastructure/database/schema.sql
-- Versión del esquema: 1
--
-- Convenciones:
--   * Tablas STRICT: SQLite rechaza tipos incorrectos (ej. texto en INTEGER).
--   * Fechas en TEXT con formato ISO 'AAAA-MM-DD'. La regla
--     "date(x) IS x" rechaza fechas mal escritas o inexistentes.
--   * Dinero en INTEGER (pesos colombianos), nunca en REAL.
--   * Llaves foráneas con ON DELETE RESTRICT: no se borra lo referenciado.
-- =====================================================================


-- ---------------------------------------------------------------------
-- PLANTAS ELÉCTRICAS
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS plantas (
    -- Control
    id                   INTEGER PRIMARY KEY,
    numero_consecutivo   INTEGER UNIQUE CHECK (numero_consecutivo > 0),
    estado               TEXT    NOT NULL DEFAULT 'DISPONIBLE'
                         CHECK (estado IN ('DISPONIBLE', 'ALQUILADA', 'EN_MANTENIMIENTO',
                                           'RETIRADA', 'VENDIDA', 'DADA_DE_BAJA')),
    fecha_registro       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),

    -- Identificación
    marca                TEXT    NOT NULL CHECK (length(trim(marca)) > 0),
    modelo               TEXT,
    numero_serie         TEXT    UNIQUE,

    -- Datos eléctricos
    potencia_kva         REAL    NOT NULL CHECK (potencia_kva > 0),
    potencia_kw          REAL    CHECK (potencia_kw IS NULL OR potencia_kw > 0),
    voltaje              TEXT,
    fases                INTEGER CHECK (fases IS NULL OR fases IN (1, 3)),

    -- Combustible
    tipo_combustible     TEXT    CHECK (tipo_combustible IS NULL
                                        OR tipo_combustible IN ('DIESEL', 'GASOLINA', 'GAS')),
    capacidad_tanque_gal REAL    CHECK (capacidad_tanque_gal IS NULL OR capacidad_tanque_gal > 0),

    -- Operativo y financiero
    fecha_adquisicion    TEXT    CHECK (date(fecha_adquisicion) IS fecha_adquisicion),
    valor_compra         INTEGER CHECK (valor_compra IS NULL OR valor_compra >= 0),
    horometro_inicial    INTEGER NOT NULL DEFAULT 0 CHECK (horometro_inicial >= 0),
    observaciones        TEXT,

    -- Regla de consistencia (defensa en profundidad): las plantas fuera de
    -- operación NO tienen número, y las que están en operación SÍ lo tienen.
    CHECK ((estado IN ('RETIRADA', 'VENDIDA', 'DADA_DE_BAJA')) = (numero_consecutivo IS NULL))
) STRICT;

CREATE INDEX IF NOT EXISTS idx_plantas_estado ON plantas (estado);


-- ---------------------------------------------------------------------
-- HISTORIAL DE CONSECUTIVOS ("dorsales" que ha tenido cada planta)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS historial_consecutivos (
    id                INTEGER PRIMARY KEY,
    planta_id         INTEGER NOT NULL REFERENCES plantas (id) ON DELETE RESTRICT,
    numero            INTEGER NOT NULL CHECK (numero > 0),
    fecha_asignacion  TEXT    NOT NULL CHECK (date(fecha_asignacion) IS fecha_asignacion),
    fecha_liberacion  TEXT    CHECK (date(fecha_liberacion) IS fecha_liberacion),
    motivo_liberacion TEXT,
    CHECK (fecha_liberacion IS NULL OR fecha_liberacion >= fecha_asignacion)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_hist_consec_numero ON historial_consecutivos (numero);
CREATE INDEX IF NOT EXISTS idx_hist_consec_planta ON historial_consecutivos (planta_id);

-- Índices parciales: como máximo UN registro abierto por planta y por número.
CREATE UNIQUE INDEX IF NOT EXISTS uq_hist_consec_planta_abierto
    ON historial_consecutivos (planta_id) WHERE fecha_liberacion IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_hist_consec_numero_abierto
    ON historial_consecutivos (numero) WHERE fecha_liberacion IS NULL;


-- ---------------------------------------------------------------------
-- HISTORIAL DE ESTADOS (línea de tiempo de cada planta)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS historial_estados (
    id              INTEGER PRIMARY KEY,
    planta_id       INTEGER NOT NULL REFERENCES plantas (id) ON DELETE RESTRICT,
    estado_anterior TEXT    CHECK (estado_anterior IS NULL
                                   OR estado_anterior IN ('DISPONIBLE', 'ALQUILADA',
                                       'EN_MANTENIMIENTO', 'RETIRADA', 'VENDIDA', 'DADA_DE_BAJA')),
    estado_nuevo    TEXT    NOT NULL
                            CHECK (estado_nuevo IN ('DISPONIBLE', 'ALQUILADA',
                                       'EN_MANTENIMIENTO', 'RETIRADA', 'VENDIDA', 'DADA_DE_BAJA')),
    fecha           TEXT    NOT NULL CHECK (date(fecha) IS fecha),
    motivo          TEXT
) STRICT;

CREATE INDEX IF NOT EXISTS idx_hist_estados_planta ON historial_estados (planta_id, fecha);


-- ---------------------------------------------------------------------
-- PROVEEDORES
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS proveedores (
    id       INTEGER PRIMARY KEY,
    nit      TEXT    UNIQUE,
    nombre   TEXT    NOT NULL CHECK (length(trim(nombre)) > 0),
    telefono TEXT,
    activo   INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
) STRICT;


-- ---------------------------------------------------------------------
-- CATEGORÍAS DE GASTO (catálogo editable por el usuario)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS categorias_gasto (
    id     INTEGER PRIMARY KEY,
    nombre TEXT    NOT NULL UNIQUE CHECK (length(trim(nombre)) > 0),
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
) STRICT;

INSERT OR IGNORE INTO categorias_gasto (nombre) VALUES
    ('Filtros'),
    ('Repuestos'),
    ('Aceite y lubricantes'),
    ('Mano de obra'),
    ('Otros');


-- ---------------------------------------------------------------------
-- FACTURAS DE PROVEEDOR (el "ticket" que puede repartirse entre plantas)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS facturas_proveedor (
    id             INTEGER PRIMARY KEY,
    proveedor_id   INTEGER NOT NULL REFERENCES proveedores (id) ON DELETE RESTRICT,
    numero_factura TEXT    NOT NULL CHECK (length(trim(numero_factura)) > 0),
    fecha_factura  TEXT    NOT NULL CHECK (date(fecha_factura) IS fecha_factura),
    valor_total    INTEGER NOT NULL CHECK (valor_total >= 0),
    observaciones  TEXT,
    UNIQUE (proveedor_id, numero_factura)
) STRICT;


-- ---------------------------------------------------------------------
-- MANTENIMIENTOS
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mantenimientos (
    id            INTEGER PRIMARY KEY,
    planta_id     INTEGER NOT NULL REFERENCES plantas (id) ON DELETE RESTRICT,
    fecha         TEXT    NOT NULL CHECK (date(fecha) IS fecha),
    tipo          TEXT    NOT NULL CHECK (tipo IN ('PREVENTIVO', 'CORRECTIVO')),
    horometro     INTEGER CHECK (horometro IS NULL OR horometro >= 0),
    tecnico       TEXT,
    descripcion   TEXT    NOT NULL CHECK (length(trim(descripcion)) > 0),
    proxima_fecha TEXT    CHECK (date(proxima_fecha) IS proxima_fecha),
    CHECK (proxima_fecha IS NULL OR proxima_fecha >= fecha)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_mantenimientos_planta ON mantenimientos (planta_id, fecha);


-- ---------------------------------------------------------------------
-- GASTOS (cada ítem imputado a una planta; factura opcional)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gastos (
    id               INTEGER PRIMARY KEY,
    planta_id        INTEGER NOT NULL REFERENCES plantas (id) ON DELETE RESTRICT,
    categoria_id     INTEGER NOT NULL REFERENCES categorias_gasto (id) ON DELETE RESTRICT,
    factura_id       INTEGER REFERENCES facturas_proveedor (id) ON DELETE RESTRICT,
    mantenimiento_id INTEGER REFERENCES mantenimientos (id) ON DELETE RESTRICT,
    fecha            TEXT    NOT NULL CHECK (date(fecha) IS fecha),
    descripcion      TEXT    NOT NULL CHECK (length(trim(descripcion)) > 0),
    cantidad         REAL    NOT NULL DEFAULT 1 CHECK (cantidad > 0),
    unidad           TEXT,
    valor_total      INTEGER NOT NULL CHECK (valor_total > 0),
    anulado          INTEGER NOT NULL DEFAULT 0 CHECK (anulado IN (0, 1)),
    motivo_anulacion TEXT,
    fecha_registro   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    -- Anular exige explicar por qué.
    CHECK (anulado = 0 OR length(trim(coalesce(motivo_anulacion, ''))) > 0)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_gastos_planta_fecha ON gastos (planta_id, fecha);
CREATE INDEX IF NOT EXISTS idx_gastos_factura ON gastos (factura_id);
CREATE INDEX IF NOT EXISTS idx_gastos_mantenimiento ON gastos (mantenimiento_id);
