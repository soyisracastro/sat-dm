-- 003_ieps_trasladado.sql
-- Añade la columna `ieps_trasladado` (Impuesto Especial sobre Producción y
-- Servicios, código SAT 003). Antes solo extraíamos IVA al 16% (código 002),
-- pero el IEPS también se traslada en CFDIs de telecomunicaciones, bebidas,
-- tabaco, combustibles, etc. — sin sumarlo, la fórmula de integridad
-- (Total = SubTotal − Descuento + Trasl. − Ret.) levanta un falso positivo.
--
-- Las filas existentes quedan en 0 (DEFAULT). Si el usuario quiere el dato
-- correcto puede recargar los XMLs (deduplicación por UUID los re-procesa
-- con el parser nuevo).

ALTER TABLE cfdis ADD COLUMN ieps_trasladado REAL DEFAULT 0;

-- SQLite NO aplica DEFAULT retroactivamente a filas existentes (quedan NULL);
-- las normalizamos a 0 para que las queries con SUM no se rompan.
UPDATE cfdis SET ieps_trasladado = 0 WHERE ieps_trasladado IS NULL;
