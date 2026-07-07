-- 007_mi_rfc.sql
-- Aísla el buffer del procesador por empresa: cada fila gana `mi_rfc` (el RFC
-- de la empresa que la cargó) y todas las queries del procesador se acotan a
-- la empresa activa.
--
-- La PK de `cfdis` pasa de `uuid` a `(uuid, mi_rfc)`: un mismo CFDI puede
-- pertenecer legítimamente a DOS empresas del catálogo (una emisora y una
-- receptora) con `direccion` distinta en cada copia. SQLite no permite cambiar
-- PK ni FKs con ALTER → rebuild completo de las 5 tablas. Las 4 hijas también
-- ganan `mi_rfc` con FK compuesta: los reportes de Pagos consultan
-- `pagos_relaciones` sin pasar por `cfdis`, y sin FK compuesta el CASCADE al
-- borrar el buffer de una empresa destruiría filas de otra.
--
-- Las filas existentes quedan con `mi_rfc = ''`; el hook Python
-- `db._asignar_dueno_legacy()` las asigna a la empresa default del catálogo
-- (o las purga si no hay default — el buffer es una caché re-cargable).
--
-- El INSERT..SELECT usa lista de columnas EXPLÍCITA: el orden físico de
-- `cfdis` varía según si la DB nació en 001 o recibió 002/003/006 por ALTER.

PRAGMA foreign_keys=OFF;

-- ---------------------------------------------------------------- cfdis
CREATE TABLE cfdis_new (
    uuid TEXT NOT NULL,
    mi_rfc TEXT NOT NULL DEFAULT '',
    file_name TEXT,
    version TEXT,
    tipo TEXT,
    fecha TEXT,
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
    ieps_trasladado REAL DEFAULT 0,
    iva_retenido REAL,
    isr_retenido REAL,
    forma_pago TEXT,
    metodo_pago TEXT,
    moneda TEXT,
    tipo_cambio REAL,
    lugar_expedicion TEXT,
    direccion TEXT,
    estado_sat TEXT,
    validado_en TEXT,
    raw_json TEXT,
    warnings_json TEXT,
    cargado_en TEXT,
    emisor_en_lista_negra TEXT,
    emisor_listas_match TEXT,
    receptor_en_lista_negra TEXT,
    receptor_listas_match TEXT,
    validado_listas_en TEXT,
    PRIMARY KEY (uuid, mi_rfc)
);

INSERT INTO cfdis_new (
    uuid, file_name, version, tipo, fecha, fecha_timbrado, serie, folio,
    emisor_rfc, emisor_nombre, emisor_regimen_fiscal,
    receptor_rfc, receptor_nombre, receptor_uso_cfdi,
    sub_total, descuento, total,
    iva_trasladado, ieps_trasladado, iva_retenido, isr_retenido,
    forma_pago, metodo_pago, moneda, tipo_cambio, lugar_expedicion,
    direccion, estado_sat, validado_en, raw_json, warnings_json, cargado_en,
    emisor_en_lista_negra, emisor_listas_match,
    receptor_en_lista_negra, receptor_listas_match, validado_listas_en
)
SELECT
    uuid, file_name, version, tipo, fecha, fecha_timbrado, serie, folio,
    emisor_rfc, emisor_nombre, emisor_regimen_fiscal,
    receptor_rfc, receptor_nombre, receptor_uso_cfdi,
    sub_total, descuento, total,
    iva_trasladado, ieps_trasladado, iva_retenido, isr_retenido,
    forma_pago, metodo_pago, moneda, tipo_cambio, lugar_expedicion,
    direccion, estado_sat, validado_en, raw_json, warnings_json, cargado_en,
    emisor_en_lista_negra, emisor_listas_match,
    receptor_en_lista_negra, receptor_listas_match, validado_listas_en
FROM cfdis;

-- ------------------------------------------------------------- conceptos
CREATE TABLE conceptos_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cfdi_uuid TEXT NOT NULL,
    mi_rfc TEXT NOT NULL DEFAULT '',
    clave_prod_serv TEXT,
    descripcion TEXT,
    cantidad REAL,
    clave_unidad TEXT,
    unidad TEXT,
    valor_unitario REAL,
    importe REAL,
    descuento REAL,
    FOREIGN KEY (cfdi_uuid, mi_rfc) REFERENCES cfdis(uuid, mi_rfc) ON DELETE CASCADE
);

INSERT INTO conceptos_new (
    id, cfdi_uuid, clave_prod_serv, descripcion, cantidad,
    clave_unidad, unidad, valor_unitario, importe, descuento
)
SELECT
    id, cfdi_uuid, clave_prod_serv, descripcion, cantidad,
    clave_unidad, unidad, valor_unitario, importe, descuento
FROM conceptos;

-- ------------------------------------------------------ pagos_relaciones
CREATE TABLE pagos_relaciones_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cfdi_pago_uuid TEXT NOT NULL,
    mi_rfc TEXT NOT NULL DEFAULT '',
    cfdi_pago_fecha_pago TEXT NOT NULL,
    cfdi_pago_monto REAL,
    cfdi_pago_forma TEXT,
    cfdi_pago_moneda TEXT,
    docto_uuid TEXT NOT NULL,
    docto_serie TEXT,
    docto_folio TEXT,
    docto_metodo_pago TEXT,
    docto_num_parcialidad INTEGER,
    docto_imp_saldo_ant REAL,
    docto_imp_pagado REAL,
    docto_imp_saldo_insoluto REAL,
    docto_moneda TEXT,
    FOREIGN KEY (cfdi_pago_uuid, mi_rfc) REFERENCES cfdis(uuid, mi_rfc) ON DELETE CASCADE
);

INSERT INTO pagos_relaciones_new (
    id, cfdi_pago_uuid, cfdi_pago_fecha_pago, cfdi_pago_monto,
    cfdi_pago_forma, cfdi_pago_moneda,
    docto_uuid, docto_serie, docto_folio, docto_metodo_pago,
    docto_num_parcialidad, docto_imp_saldo_ant, docto_imp_pagado,
    docto_imp_saldo_insoluto, docto_moneda
)
SELECT
    id, cfdi_pago_uuid, cfdi_pago_fecha_pago, cfdi_pago_monto,
    cfdi_pago_forma, cfdi_pago_moneda,
    docto_uuid, docto_serie, docto_folio, docto_metodo_pago,
    docto_num_parcialidad, docto_imp_saldo_ant, docto_imp_pagado,
    docto_imp_saldo_insoluto, docto_moneda
FROM pagos_relaciones;

-- -------------------------------------------------------- nomina_recibos
CREATE TABLE nomina_recibos_new (
    cfdi_uuid TEXT NOT NULL,
    mi_rfc TEXT NOT NULL DEFAULT '',
    registro_patronal TEXT,
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
    tipo_nomina TEXT,
    fecha_pago TEXT,
    fecha_inicial_pago TEXT,
    fecha_final_pago TEXT,
    num_dias_pagados REAL DEFAULT 0,
    total_percepciones REAL DEFAULT 0,
    total_deducciones REAL DEFAULT 0,
    total_otros_pagos REAL DEFAULT 0,
    PRIMARY KEY (cfdi_uuid, mi_rfc),
    FOREIGN KEY (cfdi_uuid, mi_rfc) REFERENCES cfdis(uuid, mi_rfc) ON DELETE CASCADE
);

INSERT INTO nomina_recibos_new (
    cfdi_uuid, registro_patronal, curp, nss, num_empleado, puesto,
    departamento, tipo_contrato, tipo_regimen, tipo_jornada,
    periodicidad_pago, fecha_inicio_rel_laboral, antiguedad,
    salario_base_cot_apor, salario_diario_integrado, riesgo_trabajo,
    banco, cuenta_bancaria, sindicalizado, clave_ent_fed,
    tipo_nomina, fecha_pago, fecha_inicial_pago, fecha_final_pago,
    num_dias_pagados, total_percepciones, total_deducciones, total_otros_pagos
)
SELECT
    cfdi_uuid, registro_patronal, curp, nss, num_empleado, puesto,
    departamento, tipo_contrato, tipo_regimen, tipo_jornada,
    periodicidad_pago, fecha_inicio_rel_laboral, antiguedad,
    salario_base_cot_apor, salario_diario_integrado, riesgo_trabajo,
    banco, cuenta_bancaria, sindicalizado, clave_ent_fed,
    tipo_nomina, fecha_pago, fecha_inicial_pago, fecha_final_pago,
    num_dias_pagados, total_percepciones, total_deducciones, total_otros_pagos
FROM nomina_recibos;

-- ------------------------------------------------------ nomina_conceptos
CREATE TABLE nomina_conceptos_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cfdi_uuid TEXT NOT NULL,
    mi_rfc TEXT NOT NULL DEFAULT '',
    clase TEXT NOT NULL,
    tipo_concepto TEXT,
    clave_interna TEXT,
    concepto TEXT,
    importe_gravado REAL DEFAULT 0,
    importe_exento REAL DEFAULT 0,
    importe REAL DEFAULT 0,
    subsidio_causado REAL DEFAULT 0,
    FOREIGN KEY (cfdi_uuid, mi_rfc) REFERENCES cfdis(uuid, mi_rfc) ON DELETE CASCADE
);

INSERT INTO nomina_conceptos_new (
    id, cfdi_uuid, clase, tipo_concepto, clave_interna, concepto,
    importe_gravado, importe_exento, importe, subsidio_causado
)
SELECT
    id, cfdi_uuid, clase, tipo_concepto, clave_interna, concepto,
    importe_gravado, importe_exento, importe, subsidio_causado
FROM nomina_conceptos;

-- ------------------------------------------------------- swap + índices
DROP TABLE conceptos;
DROP TABLE pagos_relaciones;
DROP TABLE nomina_conceptos;
DROP TABLE nomina_recibos;
DROP TABLE cfdis;

ALTER TABLE cfdis_new RENAME TO cfdis;
ALTER TABLE conceptos_new RENAME TO conceptos;
ALTER TABLE pagos_relaciones_new RENAME TO pagos_relaciones;
ALTER TABLE nomina_recibos_new RENAME TO nomina_recibos;
ALTER TABLE nomina_conceptos_new RENAME TO nomina_conceptos;

-- Los índices de 001/002/004/005/006 se fueron con los DROP; se recrean
-- todos + los nuevos por empresa.
CREATE INDEX IF NOT EXISTS idx_cfdis_tipo ON cfdis(tipo);
CREATE INDEX IF NOT EXISTS idx_cfdis_fecha ON cfdis(fecha);
CREATE INDEX IF NOT EXISTS idx_cfdis_emisor_rfc ON cfdis(emisor_rfc);
CREATE INDEX IF NOT EXISTS idx_cfdis_receptor_rfc ON cfdis(receptor_rfc);
CREATE INDEX IF NOT EXISTS idx_cfdis_estado_sat ON cfdis(estado_sat);
CREATE INDEX IF NOT EXISTS idx_cfdis_direccion ON cfdis(direccion);
CREATE INDEX IF NOT EXISTS idx_cfdis_emisor_lista_negra
    ON cfdis(emisor_en_lista_negra);
CREATE INDEX IF NOT EXISTS idx_cfdis_receptor_lista_negra
    ON cfdis(receptor_en_lista_negra);
CREATE INDEX IF NOT EXISTS idx_cfdis_mi_rfc ON cfdis(mi_rfc, fecha);

CREATE INDEX IF NOT EXISTS idx_conceptos_cfdi_uuid ON conceptos(cfdi_uuid, mi_rfc);

CREATE INDEX IF NOT EXISTS idx_pagos_rel_pago ON pagos_relaciones(cfdi_pago_uuid, mi_rfc);
CREATE INDEX IF NOT EXISTS idx_pagos_rel_docto ON pagos_relaciones(docto_uuid, mi_rfc);

CREATE INDEX IF NOT EXISTS idx_nom_rec_nss ON nomina_recibos(nss);
CREATE INDEX IF NOT EXISTS idx_nom_rec_fecha_pago ON nomina_recibos(fecha_pago);
CREATE INDEX IF NOT EXISTS idx_nom_rec_periodicidad ON nomina_recibos(periodicidad_pago);

CREATE INDEX IF NOT EXISTS idx_nom_conc_cfdi ON nomina_conceptos(cfdi_uuid, mi_rfc);
CREATE INDEX IF NOT EXISTS idx_nom_conc_clase ON nomina_conceptos(clase);
CREATE INDEX IF NOT EXISTS idx_nom_conc_tipo ON nomina_conceptos(clase, tipo_concepto);

PRAGMA foreign_keys=ON;
