-- 004_pagos_relaciones.sql
-- Tabla normalizada de relaciones complemento-de-pago ↔ factura PPD.
--
-- Hasta la migración 003 los CFDIs tipo P guardaban su `datos_pago` solo
-- dentro de `cfdis.raw_json`. Eso es suficiente para mostrar el CFDI tal cual
-- pero NO para hacer queries SQL del tipo "qué facturas PPD están conciliadas",
-- "cuánto saldo insoluto hay por receptor" o "cuáles complementos son
-- extemporáneos". Esta tabla extrae cada `DoctoRelacionado` a su propia fila
-- para que los reportes del procesador de Pagos sean SQL puro con índices.
--
-- Schema:
--   - cfdi_pago_*  : campos del CFDI tipo P (Pago wrapper).
--   - docto_*      : campos del documento PPD relacionado (uno por fila).
--   - 1 CFDI tipo P puede tener N filas (N documentos relacionados).
--   - 1 PPD puede aparecer en N filas (N complementos parciales).

CREATE TABLE IF NOT EXISTS pagos_relaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cfdi_pago_uuid TEXT NOT NULL,
    cfdi_pago_fecha_pago TEXT NOT NULL,         -- FechaPago (ISO)
    cfdi_pago_monto REAL,                       -- Monto total del Pago
    cfdi_pago_forma TEXT,                       -- FormaDePagoP
    cfdi_pago_moneda TEXT,
    docto_uuid TEXT NOT NULL,                   -- IdDocumento (UUID del PPD)
    docto_serie TEXT,
    docto_folio TEXT,
    docto_metodo_pago TEXT,                     -- MetodoDePagoDR (PUE/PPD)
    docto_num_parcialidad INTEGER,
    docto_imp_saldo_ant REAL,
    docto_imp_pagado REAL,                      -- CRÍTICO: monto asignado a ESTE doc
    docto_imp_saldo_insoluto REAL,
    docto_moneda TEXT,
    FOREIGN KEY (cfdi_pago_uuid) REFERENCES cfdis(uuid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pagos_rel_pago ON pagos_relaciones(cfdi_pago_uuid);
CREATE INDEX IF NOT EXISTS idx_pagos_rel_docto ON pagos_relaciones(docto_uuid);

-- NOTA: la repoblación de filas existentes (CFDIs tipo P ya cargados antes
-- de esta migración) la hace `db.py:_repoblar_pagos_relaciones()` después
-- de aplicar la migración. SQLite no tiene un parser JSON tan flexible
-- como para hacerlo en SQL puro sin acoplarse a la versión de JSON1.
