-- 006_listas_negras.sql
-- Agrega resultado de validación contra listas negras del SAT (Art. 69 y 69-B
-- del CFF) por emisor y receptor de cada CFDI. La fuente de datos es la API
-- de todoconta-apps (Vercel cron mensual → Supabase). Aquí solo persistimos
-- el último resultado obtenido por RFC, para poder filtrar/ordenar en el
-- procesador sin volver a llamar al endpoint en cada render.
--
-- Dos columnas por lado (emisor/receptor) porque el procesador maneja CFDIs
-- emitidos y recibidos: un CFDI puede tener problemas en cualquiera de los dos.
-- El campo `*_listas_match` guarda el JSON crudo del match (situación 69-B,
-- supuestos 69, fechas) para mostrar el detalle en la fila expandida.

ALTER TABLE cfdis ADD COLUMN emisor_en_lista_negra TEXT;
ALTER TABLE cfdis ADD COLUMN emisor_listas_match TEXT;
ALTER TABLE cfdis ADD COLUMN receptor_en_lista_negra TEXT;
ALTER TABLE cfdis ADD COLUMN receptor_listas_match TEXT;
ALTER TABLE cfdis ADD COLUMN validado_listas_en TEXT;

CREATE INDEX IF NOT EXISTS idx_cfdis_emisor_lista_negra
    ON cfdis(emisor_en_lista_negra);
CREATE INDEX IF NOT EXISTS idx_cfdis_receptor_lista_negra
    ON cfdis(receptor_en_lista_negra);
