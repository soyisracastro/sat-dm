-- 009_diot_deducible.sql
-- Flags editables por comprobante para Comprobantes → Procesador de CFDI:
--
-- · incluir_diot: interruptor «pasa a la DIOT» de los CFDIs elegibles
--   (recibidos de tipo I/E, misma regla que el prellenado). Default 1 =
--   pasa; el prellenado de la DIOT ignora las filas en 0. En filas no
--   elegibles (P/N/T y emitidos) el valor no tiene efecto.
-- · deducible: clasificación manual 'Deducible' | 'No deducible'.
--   NULL = «Sin analizar» (default para filas nuevas Y existentes; el
--   análisis asistido por IA llegará en un PR posterior).

ALTER TABLE cfdis ADD COLUMN incluir_diot INTEGER NOT NULL DEFAULT 1;
ALTER TABLE cfdis ADD COLUMN deducible TEXT;
