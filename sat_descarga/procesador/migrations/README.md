# Migraciones SQL del procesador

Cada archivo `NNN_descripcion.sql` se aplica en orden al levantar el agente. El
runner (`db._aplicar_migraciones_pendientes`) lee `_meta.schema_version`,
detecta las pendientes (> versión actual) y las ejecuta dentro de una
transacción atómica.

## Convención

- Nombre: `NNN_descripcion.sql` (3 dígitos consecutivos, snake_case).
- La primera línea es un comentario `-- NNN_descripcion.sql`.
- El cuerpo es SQLite estándar — no Postgres (no `JSONB`, no `uuid_generate_v4()`).
- **No modifiques archivos ya aplicados en producción.** Si necesitas
  corregir algo, crea una migración nueva.

## Crear una migración nueva

1. Sigue la numeración consecutiva (ej. `003_pagos_relaciones.sql`).
2. Usa `IF NOT EXISTS` / `IF EXISTS` para que sea idempotente.
3. Si añades columna a una tabla existente, usa `ALTER TABLE ... ADD COLUMN`
   — SQLite no soporta `DROP COLUMN` antes de 3.35 (limitación a tener en
   cuenta para mantener migraciones reversibles vía nueva tabla + copy).
4. Probar:
   - Suite Python: `pytest tests/test_procesador_cfdi.py` (cubre creación
     desde cero y migración v→v+1 vía fixture).
   - Manual: borrar `~/.sat-descarga/procesador.db`, reabrir el agente y
     verificar logs `[procesador] aplicando migración NNN_*.sql`.

## Por qué SQLite y no Postgres + Supabase

`sat-descarga-masiva` corre 100% local (el agente Python es un proceso del
Electron). No hay backend remoto ni servicio gestionado: SQLite es la
elección natural (zero-config, archivo en disco, ACID).

Si en el futuro app.todoconta.com sincroniza este buffer en la nube, esas
migraciones vivirán en `apps/web/supabase/migrations/` (Postgres) — paralelas
a estas, no compartidas.
