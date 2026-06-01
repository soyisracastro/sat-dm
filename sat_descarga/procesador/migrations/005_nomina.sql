-- 005_nomina.sql
-- Tablas normalizadas para CFDIs de Nómina (Complemento de Nómina 1.2 Revisión E).
--
-- Hasta la migración 004 los CFDIs tipo N solo se guardaban en `cfdis` con su
-- complemento serializado dentro de `raw_json`. Eso era suficiente para
-- mostrarlos pero NO para queries SQL del tipo "ISR retenido por empleado y
-- mes" o "conciliación IMSS por NSS". Esta migración extrae:
--   - 1 fila por CFDI N en `nomina_recibos` (datos del trabajador + recibo).
--   - N filas por CFDI N en `nomina_conceptos` (Percepcion / Deduccion / OtroPago).
--
-- La repoblación de filas existentes (CFDIs tipo N ya cargados antes de esta
-- migración) la hace `db.py:_repoblar_nomina()` después de aplicar el SQL.
-- Solo se repoblan los CFDIs cuyo `raw_json` ya tiene `datos_nomina` — los
-- cargados pre-PR #3 no, y el usuario tendrá que recargarlos para verlos
-- en la vista de nómina.

CREATE TABLE IF NOT EXISTS nomina_recibos (
    cfdi_uuid TEXT PRIMARY KEY,
    -- Emisor del complemento (patrón)
    registro_patronal TEXT,
    -- Trabajador
    curp TEXT,
    nss TEXT,
    num_empleado TEXT,
    puesto TEXT,
    departamento TEXT,
    tipo_contrato TEXT,
    tipo_regimen TEXT,
    tipo_jornada TEXT,
    periodicidad_pago TEXT,
    fecha_inicio_rel_laboral TEXT,
    antiguedad TEXT,
    salario_base_cot_apor REAL DEFAULT 0,
    salario_diario_integrado REAL DEFAULT 0,
    riesgo_trabajo TEXT,
    banco TEXT,
    cuenta_bancaria TEXT,
    sindicalizado TEXT,
    clave_ent_fed TEXT,
    -- Recibo
    tipo_nomina TEXT,                       -- 'O' (ordinaria) | 'E' (extraordinaria)
    fecha_pago TEXT,
    fecha_inicial_pago TEXT,
    fecha_final_pago TEXT,
    num_dias_pagados REAL DEFAULT 0,
    total_percepciones REAL DEFAULT 0,
    total_deducciones REAL DEFAULT 0,
    total_otros_pagos REAL DEFAULT 0,
    FOREIGN KEY (cfdi_uuid) REFERENCES cfdis(uuid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_nom_rec_nss ON nomina_recibos(nss);
CREATE INDEX IF NOT EXISTS idx_nom_rec_fecha_pago ON nomina_recibos(fecha_pago);
CREATE INDEX IF NOT EXISTS idx_nom_rec_periodicidad ON nomina_recibos(periodicidad_pago);

CREATE TABLE IF NOT EXISTS nomina_conceptos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cfdi_uuid TEXT NOT NULL,
    clase TEXT NOT NULL,                    -- 'Percepcion' | 'Deduccion' | 'OtroPago'
    tipo_concepto TEXT,                     -- clave SAT (ej. '001', '002')
    clave_interna TEXT,
    concepto TEXT,
    importe_gravado REAL DEFAULT 0,
    importe_exento REAL DEFAULT 0,
    importe REAL DEFAULT 0,
    subsidio_causado REAL DEFAULT 0,
    FOREIGN KEY (cfdi_uuid) REFERENCES cfdis(uuid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_nom_conc_cfdi ON nomina_conceptos(cfdi_uuid);
CREATE INDEX IF NOT EXISTS idx_nom_conc_clase ON nomina_conceptos(clase);
CREATE INDEX IF NOT EXISTS idx_nom_conc_tipo ON nomina_conceptos(clase, tipo_concepto);
