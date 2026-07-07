-- 008_desglose_iva.sql
-- Añade el desglose de IVA por tasa (bases 16%, 8%, 0% y exento, más el
-- importe trasladado al 8%) que necesita el prellenado de la DIOT
-- (docs/diot-2025.md). El parser lo extrae del nodo `Impuestos` global.
--
-- Las filas existentes quedan en NULL a propósito — el raw_json de cargas
-- anteriores NO trae el desglose, así que no hay backfill posible. NULL
-- distingue "cargado con parser viejo" de "parseado y sin ese impuesto" (0):
-- la agregación de la DIOT estima la base 16% como iva_trasladado/0.16 en
-- filas NULL y avisa al usuario que recargue los XMLs para el dato exacto.

ALTER TABLE cfdis ADD COLUMN base_iva_16 REAL;
ALTER TABLE cfdis ADD COLUMN base_iva_8 REAL;
ALTER TABLE cfdis ADD COLUMN iva_trasladado_8 REAL;
ALTER TABLE cfdis ADD COLUMN base_iva_0 REAL;
ALTER TABLE cfdis ADD COLUMN base_exento REAL;
