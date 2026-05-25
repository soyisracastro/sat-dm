# Changelog

## v1.2.0 (2026-05-25)

Reorganización del proyecto **por canal de acceso** y **CLI unificado**.

### Cambios

- **Estructura por subpaquetes** en `sat_descarga/`: `core/` (config, fiel, http_client),
  `webservice/` (auth, solicitud, verificacion, descarga, client), `portal/`
  (login, cfdi, constancia), `utils/` (xml_reader, metadata, organizador, validacion),
  `api/` (server, hosted). El paquete `cli/` se movió dentro de `sat_descarga/cli/`.
- **Login SSO extraído** a `portal/login.py` (`iniciar_sesion_ciec` / `iniciar_sesion_fiel`),
  compartido por todos los scrapers del portal.
- **CLI unificado**: las descargas son subcomandos del grupo `descargar`:
  `sat-dm descargar cfdi` (Web Service), `sat-dm descargar ciec` (portal CFDIs) y
  `sat-dm descargar constancia --metodo ciec|fiel`. Se eliminaron los scripts
  `prueba_*.py` de la raíz (eran los runners reales, no tests).
- **API pública estable** re-exportada en `sat_descarga/__init__.py`:
  `descargar_cfdi`, `FIEL`, `descargar_cfdi_ciec`, `descargar_constancia_ciec/fiel`, etc.
- **Tests**: actualizados a las nuevas rutas + nuevos tests de portal (lógica pura) y CLI.

### Cambios incompatibles

- `sat-dm descargar` ahora es un **grupo**: usar `sat-dm descargar cfdi` para el flujo
  anterior de Web Service.
- Los imports por submódulo cambian (p. ej. `sat_descarga.ciec` → `sat_descarga.portal.cfdi`,
  `sat_descarga.validacion` → `sat_descarga.utils.validacion`). La API por la raíz
  (`from sat_descarga import ...`) se mantiene.

---

## v1.1.0 (2026-05-25)

Descarga de la **Constancia de Situación Fiscal (CSF)** vía el portal del SAT, con
login CIEC o e.firma.

### Nuevas funcionalidades

- **Constancia de Situación Fiscal**: descarga el PDF de la constancia mediante
  scraping del portal (sin Web Service), con dos métodos de login:
  - **CIEC** (RFC + contraseña; el usuario resuelve el captcha).
  - **e.firma / FIEL** (`.cer` + `.key` + contraseña): **100% automático, sin
    captcha** — ideal para automatización/desatendido.
  - API: `descargar_constancia_ciec(rfc, ciec)` y `descargar_constancia_fiel(cer, key, password)`.
  - Endpoint `POST /constancia/descargar`; runners `prueba_constancia.py` y `prueba_constancia_fiel.py`.
- **Login SSO reutilizable**: `iniciar_sesion_ciec()` e `iniciar_sesion_fiel()` en
  `sat_descarga/ciec.py`, compartidos por los scrapers (CFDI, constancia y futuros).
  El flujo CFDI delega en el helper sin cambiar su comportamiento.

### Notas técnicas

- El botón "Generar Constancia" es JSF/PrimeFaces dentro de un iframe (`rfcampc.siat`);
  el PDF abre en un popup (`IdcGeneraConstancia.jsf`). e.firma entra por el lanzador
  (`tipoLogeo=c`) + botón `#buttonFiel`.
- El servidor del SAT usa TLS con clave DH muy pequeña que Node rechaza; el PDF se
  captura desde el navegador (Chromium) en vez de una petición HTTP separada.

### Archivos nuevos

- `sat_descarga/constancia.py` — cliente de la CSF (CIEC + e.firma)
- `prueba_constancia.py` / `prueba_constancia_fiel.py` — runners

---

## v1.0.0 (2026-05-24)

Interfaz web (UI + API), descarga vía CIEC sin e-firma, y madurez del proyecto.

### Nuevas funcionalidades

- **Descarga vía CIEC (portal web, sin e-firma)**: para contribuyentes que no cuentan con FIEL
  - `sat_descarga/ciec.py` — cliente Playwright headful (el usuario resuelve el captcha)
  - Recibidos (día por día) y Emitidos (rango); modo "ambos" con un solo captcha
  - Descarga item por item vía `RecuperaCfdi.aspx?Datos=`; subcarpetas `recibidos/` y `emitidos/`
  - Detección de cuota diaria del portal (se detiene tras 3 fallos seguidos)
  - Runner de ejemplo: `prueba_ciec.py RFC CIEC desde hasta [R|E|RE]`
- **Servidor FastAPI** (`localhost:8787`): expone SATDescarga vía HTTP sin que la e-firma salga de la máquina (compatible con apps web como todoconta)
  - Auth (e-firma en memoria), solicitar/verificar/descargar, folio, metadata, validación, descarga-completa, descarga-inteligente y `/ciec/descargar`
- **UI web (Next.js)**: interfaz para descarga, validación y organización de CFDIs

### Archivos nuevos

- `sat_descarga/ciec.py` — descarga vía portal CIEC (Playwright)
- `sat_descarga/server.py` — servidor FastAPI
- `ui/` — aplicación web Next.js
- `docs/protocolo-sat.md` — detalle del protocolo SOAP del Web Service y de la mecánica del portal CIEC

---

## v0.2.0 (2026-04-01)

Validación, metadata, descarga por UUID, y herramientas de organización de XMLs.

### Nuevas funcionalidades

- **Validación de CFDI ante el SAT**: verifica estatus (Vigente/Cancelado/No Encontrado) sin FIEL
  - `sat-dm validar ./xmls/` con export a CSV
  - Validación masiva con ThreadPoolExecutor (10 hilos en paralelo)
  - Endpoint `POST /validar` en FastAPI (compatible con todoconta-apps)
- **Descarga de metadata**: resumen rápido de CFDIs sin descargar XMLs
  - Hasta 1,000,000 registros por solicitud, procesados en segundos
  - Parser automático del CSV del SAT (separador `~`, encoding auto-detect)
  - `sat-dm metadata --desde --hasta --csv-export reporte.csv`
  - Flag `--local` para re-parsear metadata ya descargada
  - Deduplicación automática por UUID
- **Descarga por UUID**: `SolicitaDescargaFolio` para descargar CFDIs específicos
  - `descargar_por_uuid()` en la API Python
  - Endpoint `POST /solicitar-folio` en FastAPI
- **Organizador de XMLs**: herramientas para ordenar archivos descargados
  - `sat-dm organizar carpetas` — 9 estructuras de carpetas (RFC/año/mes, tipo/año/mes, etc.)
  - `sat-dm organizar renombrar` — 5 patrones de renombrado por contenido del XML
  - `sat-dm organizar deduplicar` — elimina duplicados por UUID (con dry-run)
  - Agrupador por versión CFDI y tipo de comprobante
- **Parser ligero de XML CFDI**: extrae headers (emisor, receptor, fecha, UUID, total) sin parseo completo, namespace-agnostic

### Correcciones

- **RFC de personas morales**: el certificado FIEL contiene `RFC_EMPRESA / RFC_REPRESENTANTE` en UniqueIdentifier; ahora toma correctamente el primero (antes tomaba el del representante legal)
- **Auto-detección de FIEL**: excluye directorios `tests/`, `.venv/` y archivos CSD del globbing

### Archivos nuevos

- `sat_descarga/validacion.py` — validación de estatus CFDI contra SAT
- `sat_descarga/metadata.py` — parser de metadata CSV del SAT
- `sat_descarga/xml_reader.py` — parser ligero de CFDI XML
- `sat_descarga/organizador.py` — organizar, renombrar, deduplicar XMLs
- `cli/validar.py` — CLI de validación masiva
- `cli/metadata_cmd.py` — CLI de descarga de metadata
- `cli/organizar.py` — CLI de organización de archivos

---

## v0.1.0 (2026-03-30)

Primera versión funcional. Descarga masiva de CFDIs del SAT vía Web Service oficial (API v1.5).

### Funcionalidades

- **Descarga masiva vía e-firma (FIEL)**: flujo completo solicitar -> verificar -> descargar
- **CLI multi-empresa**: registrar múltiples FIELs, seleccionar interactivamente o por argumentos
- **Gestión de empresas**: `empresas add`, `list`, `remove`, `default`
- **Auto-detección de FIEL**: busca archivos `.cer`, `.key` y `password.txt` automáticamente
- **Organización por RFC**: archivos FIEL en `./efirma/{RFC}/`, descargas en `./descargas/{RFC}/`
- **Fecha de vencimiento**: visible en el listado de empresas con indicador de color
- **Retomar solicitudes**: `retomar <RequestID>` para descargas interrumpidas
- **Emitidos y recibidos**: descarga individual o ambos en una sola ejecución
- **Polling automático**: backoff exponencial (30s a 5min) durante el procesamiento del SAT
- **Reintentos HTTP**: 6 reintentos con backoff para la inestabilidad SSL del SAT
- **Renovación de token**: automática antes de cada descarga (token dura ~5 min)

### Detalles técnicos

- API v1.5 del SAT (mayo 2025): firma xmldsig enveloped con C14N inclusiva
- `EstadoComprobante`: `"Vigente"`, `"Cancelado"`, `"Todos"`
- Recibidos requiere `RfcReceptor` explícito
- SOAPAction de descarga: `IDescargaMasivaTercerosService/Descargar`
- Probado con descarga real de ~950 CFDIs (emitidos + recibidos)
