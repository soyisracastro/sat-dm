# Integración TodoConta Desktop ↔ CONTPAQi Contabilidad

Documentación técnica para integrar TodoConta Desktop con **CONTPAQi Contabilidad**: enviar
**pólizas** desde los CFDIs de TodoConta hacia CONTPAQi, y **leer** información contable
(catálogo de cuentas, pólizas, saldos) para conciliación.

> **Estado**: documentación de diseño. **Nada de esto está implementado todavía.** Las secciones
> "Propuesta de implementación" describen contratos y módulos listos para ejecutar en una fase
> posterior, sin alterar la app actual.
>
> **Fuentes**: investigación hecha sobre una instalación real de **CONTPAQi Contabilidad 14.4.2**
> (`C:\Program Files (x86)\Compac`) — diccionario de BD, esquemas de importación y **type library
> del SDK** extraídos del disco; ver cada documento para la cita exacta. Notas de la brecha a la
> **v19** en `05-roadmap.md`.

## Objetivo

Cerrar el ciclo **CFDI descargado del SAT → póliza contabilizada → conciliado**, aprovechando que
TodoConta corre un agente local **en la misma máquina** donde vive CONTPAQi — algo que ninguna app
web puede hacer (`docs/presentacion-pitch.md`, Bloque 5). Regla firme heredada del pitch (línea
224): **escribir siempre por la vía que el propio CONTPAQi acepta (archivo o SDK), nunca tocando su
base de datos por dentro**.

## Documentos

| # | Documento | Qué cubre |
|---|---|---|
| — | **README.md** (este) | Visión, arquitectura, entorno detectado, comparativa de vías |
| 01 | [`01-importacion-txt-polizas.md`](01-importacion-txt-polizas.md) | **Escritura vía archivo TXT** — layout campo por campo (esquema `CT_EST_Poliza_NG`), sin licencia SDK |
| 02 | [`02-sdk-com.md`](02-sdk-com.md) | **Escritura vía SDK COM** — API `SDKCONTPAQNG` real, licencia, arquitectura de host x86/x64 |
| 03 | [`03-lectura-sql-server.md`](03-lectura-sql-server.md) | **Lectura read-only** — tablas SQL Server, conciliación UUID↔póliza |
| 04 | [`04-mapeo-cfdi-poliza.md`](04-mapeo-cfdi-poliza.md) | **Reglas contables** CFDI (`CfdiData`) → asientos |
| 05 | [`05-roadmap.md`](05-roadmap.md) | Fases, esfuerzo, riesgos, brecha 14→19, escalabilidad Aspel/Microsip |

## Dónde encaja en TodoConta

La integración vive en el **agente Python** (`sat_descarga/`), no en Electron ni en la UI. Es el
único componente con permisos para tocar código nativo / SQL local. Encaja como un dominio nuevo,
**gemelo estructural del módulo DIOT** (que ya exporta un archivo de formato fijo para un tercero):

- `sat_descarga/contpaq/` — layout, mapeo, exportador (espejo de `sat_descarga/diot/`).
- `sat_descarga/api/routers/contpaq.py` — router montado en `sat_descarga/api/server.py`, junto a
  los `include_router` existentes (mismo patrón que `routers/diot.py`).
- **Fuente de datos**: la tabla `cfdis` de `~/.sat-descarga/procesador.db`
  (`sat_descarga/procesador/db.py`), que ya guarda cada CFDI parseado (`CfdiData` en `raw_json`).

```mermaid
flowchart LR
    UI["UI Next.js<br/>(Electron)"] -- HTTP 127.0.0.1 --> AG["Agente Python<br/>FastAPI (sat_descarga)"]
    AG --> DB[("procesador.db<br/>CFDIs parseados")]
    AG -- "vía A: genera TXT" --> TXT["archivo .txt<br/>CT_EST_Poliza_NG"]
    TXT -- "importa (manual)" --> CI["CONTPAQi<br/>Contabilidad"]
    AG -- "vía B: COM (sidecar x86)" --> SDK["SDKCONTPAQNG.exe<br/>(SDK COM)"]
    SDK --> CI
    AG -- "vía C: SELECT read-only" --> SQL[("SQL Server<br/>.\\COMPAC / ct*")]
    CI --- SQL
```

## Entorno detectado (instalación 14.4.2)

| Elemento | Valor |
|---|---|
| Producto / versión | CONTPAQi Contabilidad **14.4.2** |
| Raíz de instalación | `C:\Program Files (x86)\Compac` |
| Empresas | `C:\Compac\Empresas\` (bases `ctEmpresaX` + ADD `adCtEmpresaX`) |
| Motor de BD | **SQL Server Express** (instancia típica `.\COMPAC` / `.\SQLEXPRESS`) |
| SDK | `C:\Program Files (x86)\Compac\SDK\` — **COM `SDKCONTPAQNG`** (51 clases, registrado, v14.4.2) |
| Esquemas de importación | `C:\Compac\Empresas\Esquemas\Contpaq\CT_EST_Poliza_NG.xls` y variantes |
| Diccionario de BD | `C:\Program Files (x86)\Compac\Contabilidad\BDDCONTPAQi.pdf` |
| Contabilidad Electrónica | XSD SAT en `Servidor de Aplicaciones\Extras\schemas\localxsd\` |

## Comparativa de las tres vías

| | **A) TXT** | **B) SDK COM** | **C) SQL read-only** |
|---|---|---|---|
| Dirección | Escritura | Escritura | Lectura |
| Licencia SDK | ❌ No requiere | ✅ Requiere (habilitar con distribuidor) | ❌ No requiere |
| Tiempo real | No (importación manual/semi) | Sí | Sí |
| Asocia UUID al ADD | Sí (registro `AD`) | Sí (`TSdkAsocCFDI`) | — |
| Complejidad técnica | Baja (gemelo de DIOT) | Media/alta (COM x86, host) | Baja/media |
| Riesgo | Bajo | Medio | Bajo (solo SELECT) |
| Esfuerzo estimado | 1-2 semanas | 3-4 semanas (+ licencia) | 1-2 semanas |

## Estrategia recomendada

1. **Vía C (lectura) primero** — conciliación UUID↔póliza y catálogo de cuentas. Máximo valor,
   mínimo riesgo, sin licencia. Es la "Fase 1" del pitch.
2. **Vía A (TXT) en paralelo** — pre-armado y exportación de pólizas reutilizando el molde DIOT.
   Primera capacidad de escritura, sin licencia.
3. **Vía B (SDK) como profundización** — escritura en tiempo real, condicionada a la licencia SDK.
   Reutiliza el mismo mapeo que la vía A.

Detalle y criterios de "listo para implementar" en [`05-roadmap.md`](05-roadmap.md).
