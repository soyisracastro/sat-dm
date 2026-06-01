-- 001_init.sql
-- Schema inicial del procesador de comprobantes (CFDI / Pagos / Nómina).
--
-- Tablas:
--   - cfdis     : un registro por CFDI parseado.
--   - conceptos : N por CFDI (relación 1:N).
--   - filtros   : un solo registro `key='actuales'` con los filtros activos
--                 en formato JSON.
--   - _meta     : metadatos del schema (versión, etc.).

CREATE TABLE IF NOT EXISTS cfdis (
    uuid TEXT PRIMARY KEY,
    file_name TEXT,
    version TEXT,
    tipo TEXT,
    fecha TEXT,                 -- ISO YYYY-MM-DDTHH:MM:SS
    fecha_timbrado TEXT,
    serie TEXT,
    folio TEXT,
    emisor_rfc TEXT,
    emisor_nombre TEXT,
    emisor_regimen_fiscal TEXT,
    receptor_rfc TEXT,
    receptor_nombre TEXT,
    receptor_uso_cfdi TEXT,
    sub_total REAL,
    descuento REAL,
    total REAL,
    iva_trasladado REAL,
    iva_retenido REAL,
    isr_retenido REAL,
    forma_pago TEXT,
    metodo_pago TEXT,
    moneda TEXT,
    tipo_cambio REAL,
    lugar_expedicion TEXT,
    estado_sat TEXT,            -- "Vigente" | "Cancelado" | "No encontrado" | NULL
    validado_en TEXT,
    raw_json TEXT,              -- CfdiData completo serializado
    warnings_json TEXT,         -- lista de warnings serializada
    cargado_en TEXT             -- ISO timestamp
);

CREATE INDEX IF NOT EXISTS idx_cfdis_tipo ON cfdis(tipo);
CREATE INDEX IF NOT EXISTS idx_cfdis_fecha ON cfdis(fecha);
CREATE INDEX IF NOT EXISTS idx_cfdis_emisor_rfc ON cfdis(emisor_rfc);
CREATE INDEX IF NOT EXISTS idx_cfdis_receptor_rfc ON cfdis(receptor_rfc);
CREATE INDEX IF NOT EXISTS idx_cfdis_estado_sat ON cfdis(estado_sat);

CREATE TABLE IF NOT EXISTS conceptos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cfdi_uuid TEXT NOT NULL,
    clave_prod_serv TEXT,
    descripcion TEXT,
    cantidad REAL,
    clave_unidad TEXT,
    unidad TEXT,
    valor_unitario REAL,
    importe REAL,
    descuento REAL,
    FOREIGN KEY (cfdi_uuid) REFERENCES cfdis(uuid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_conceptos_cfdi_uuid ON conceptos(cfdi_uuid);

CREATE TABLE IF NOT EXISTS filtros (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS _meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
