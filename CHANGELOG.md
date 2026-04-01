# Changelog

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
