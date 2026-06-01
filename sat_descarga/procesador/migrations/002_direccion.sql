-- 002_direccion.sql
-- Añade la columna `direccion` a `cfdis` para distinguir comprobantes
-- recibidos (yo soy receptor) vs emitidos (yo soy emisor) relativo a la
-- empresa activa. Se pobla al cargar comparando emisor/receptor con el
-- RFC activo, o se fija explícitamente cuando la carga viene del flujo
-- "Desde empresa" con tipo R/E.
--
-- Las filas existentes (pre-migración) quedan en NULL — el usuario puede
-- recargarlas si quiere usar el filtro de dirección.

ALTER TABLE cfdis ADD COLUMN direccion TEXT;

CREATE INDEX IF NOT EXISTS idx_cfdis_direccion ON cfdis(direccion);
