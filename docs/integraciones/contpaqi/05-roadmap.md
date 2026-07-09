# Roadmap de implementación — Integración CONTPAQi

Fases, esfuerzo, riesgos y criterios de "listo para implementar". Estimaciones para un
desarrollador familiarizado con el agente Python; asumen reutilizar el patrón DIOT.

## Fase 0 — Documentación (esta carpeta) ✅

Investigación y specs. Hecho: layout TXT, API del SDK, tablas SQL, mapeo contable, todo verificado
contra la instalación 14.4.2.

## Fase 1 — Lectura SQL (conciliación + catálogo) · ~1-2 semanas · sin licencia

Alcance: `03-lectura-sql-server.md`. Entrega la conciliación UUID↔póliza (el "wow" del pitch) y el
catálogo de cuentas para el configurador de mapeo.

Pasos:
1. Agregar `pymssql` a `install_requires` y a `hiddenimports` de `packaging/sat-agent.spec`.
2. `sat_descarga/contpaq/lectura.py` (descubrimiento de instancia/empresas, queries del doc 03).
3. Router `routers/contpaq.py`: `GET /contpaq/conexion/estado`, `/contpaq/cuentas`,
   `/contpaq/conciliacion`.
4. Login SQL de solo lectura documentado para el usuario.

**Listo cuando**: contra una empresa demo, la conciliación distingue correctamente CFDIs
contabilizados vs no contabilizados, y lista el catálogo de cuentas afectables.

## Fase 2 — Exportación TXT de pólizas · ~1-2 semanas (+pruebas) · sin licencia

Alcance: `01-importacion-txt-polizas.md` + `04-mapeo-cfdi-poliza.md`.

Pasos:
1. `sat_descarga/contpaq/` : `modelo.py`, `layout_poliza.py` (transcribir `CT_EST_Poliza_NG`),
   `mapeo.py`, `exportar_poliza.py` (cp1252/CRLF).
2. `ConfigCuentasContpaq` por empresa (poblada con el catálogo de la Fase 1).
3. Endpoints `POST /contpaq/polizas/preview` y `/exportar`, `GET /contpaq/esquemas`.
4. Golden file (byte a byte) + prueba de cuadre. **Validar con una importación real en CONTPAQi**
   sobre empresa demo (confirma el serializado posicional y los separadores — ver doc 01 §6).

**Listo cuando**: un CFDI de ingreso genera un TXT que CONTPAQi importa sin errores, la póliza
cuadra y el UUID queda asociado (registro `AD`).

## Fase 3 — Escritura SDK COM · ~3-4 semanas · **bloqueada por licencia SDK**

Alcance: `02-sdk-com.md`. Escritura en tiempo real + asociación de UUID al ADD.

Pasos:
1. **Habilitar licencia SDK** con CONTPAQi/distribuidor y verificar (`abreEmpresa` exitoso).
2. **Probar Opción A** (COM directo x64 → servidor out-of-process). Si falla, **Opción B**
   (sidecar Python x86 con su propio `.spec`).
3. `sat_descarga/contpaq/sdk/`: cliente COM que traduce `Poliza`/`MovimientoPoliza` a llamadas
   del SDK (reutiliza el mapeo de la Fase 2).
4. Endpoints `GET /contpaq/sdk/estado`, `POST /contpaq/sdk/polizas`.

**Listo cuando**: alta de póliza de prueba confirmada en CONTPAQi (afectada + UUID en ADD) y
reversible.

## Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| **Licencia SDK** depende de distribuidor y costo | Bloquea Fase 3 | Fases 1 y 2 no la necesitan; entregar valor sin SDK primero |
| **Bitness** agente x64 vs SDK x86 | Fase 3 | El servidor es out-of-process → probar COM directo; fallback sidecar x86 |
| **Serializado posicional del TXT** (separadores/anchos) no verificable sin importar | Fase 2 | Golden file + prueba de importación real en empresa demo antes de liberar |
| **Versiones de CONTPAQi** distintas en clientes (13/14/**19**) | Fases 2-3 | El TXT (`CT_EST_*`) es estable entre versiones; la type library del SDK **sí** cambia — re-verificar por versión |
| **Instancia/credenciales SQL** varían por instalación | Fase 1 | Asistente de descubrimiento (enumerar instancias, mapear empresas) + login read-only dedicado |
| **Encoding** (cp1252 en TXT, BSTR en COM) | Fases 2-3 | Forzar `windows-1252` en el exportador; pruebas con acentos/ñ |
| **Escritura directa a la BD** (tentación de `INSERT`) | Crítico | Prohibido: corrompe la contabilidad y anula soporte. Solo TXT/SDK. Documentado en doc 03 §3 |
| **Empaquetado PyInstaller** de drivers nativos (`pymssql`, `pywin32`/`comtypes`) | Fases 1-3 | Declarar `hiddenimports`/binaries en el `.spec`; ya hay precedente (lxml/uvicorn/playwright) |

## Brecha de versión 14.4.2 → 19 (a resolver antes de producción)

La investigación se hizo sobre **14.4.2** (instalada en el despacho). Existe descargada la
distribución **v19.1.2** (`C:\Users\israe\Downloads\CONTABILIDAD_BANCOS_1912_897\`), que trae un
**instalador dedicado del SDK NG** (`CTNGSDK\CONTPAQi_SDK.exe`) — el SDK se distribuye con el
producto en versiones recientes.

Antes de implementar la Fase 3 (y para confirmar la 2) contra clientes en v19:

1. Instalar la v19 (demo 30 días; licenciar si procede) **o** extraer sus instaladores.
2. **Re-extraer la type library** del SDK v19 y hacer diff contra la 14.4.2 documentada en el
   doc 02 (ProgID/CLSID, métodos, requisitos de licencia).
3. Verificar que los esquemas `CT_EST_Poliza_*.xls` de la v19 coinciden con lo documentado en el
   doc 01 (históricamente estables, pero confirmar).
4. Confirmar el nombre de instancia SQL y el mapa empresa→base en v19.

## Escalabilidad a otros sistemas contables

El mismo patrón (leer BD local + escribir por archivo de importación, SDK como paso profundo)
aplica a los sistemas del pitch (`docs/presentacion-pitch.md` líneas 218-222):

- **Aspel COI/SAE** — Firebird local; "interface / archivo de pólizas" → SDK Aspel.
- **Microsip** — SQL Server local; importación de pólizas.

Al implementar CONTPAQi, dejar `sat_descarga/contpaq/` con una frontera limpia (modelo `Poliza`
neutro + un "exportador"/"sink" por sistema) facilita añadir `sat_descarga/aspel/`, etc., sin
rehacer el mapeo CFDI→póliza.

## Enlace de índice (sugerencia, requiere tocar un archivo existente)

Para descubribilidad, agregar una línea en `docs/mejoras-futuras.md` o en el README del repo
apuntando a `docs/integraciones/contpaqi/`. **No se hizo** aquí para respetar la restricción de no
modificar archivos existentes; queda como acción opcional del mantenedor.
