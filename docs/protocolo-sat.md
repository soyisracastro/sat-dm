# Protocolo del SAT — notas de implementación

Detalle técnico del protocolo del SAT (conocimiento de dominio que NO se necesita
en cada sesión; por eso vive aquí y no en CLAUDE.md). Dos vías: Web Service (FIEL)
y portal CIEC (scraping).

## Web Service oficial (e-firma / FIEL)

Protocolo SOAP sobre HTTPS (WCF/Microsoft `.svc`). Autenticación **solo con e-firma**
(`.cer` + `.key` + contraseña); NO funciona con CIEC. Flujo asíncrono.

```
1. FIEL.sign()  →  auth.obtener_token()              →  Token UUID (~5 min)
2. solicitud.solicitar_descarga()                    →  RequestID
3. verificacion.verificar_solicitud() [polling]      →  PackageIDs (cuando CodEstado=3)
4. descarga.descargar_todos()                        →  ZIPs con XMLs
```

El token dura ~5 min y se renueva antes de cada descarga (el polling puede durar horas).
SSL inestable (~25% de fallos): se fuerza TLS 1.2 con `check_hostname=False` y
`verify=False`, 6 reintentos con backoff (`http_client.py`). Cliente SOAP manual con
`lxml` (`huge_tree=True`) — sin zeep/suds — para controlar namespaces y firma.

### Estados de VerificaSolicitud

| CodEstado | Significado |
|---|---|
| 1 | En cola |
| 2 | Procesando |
| 3 | Lista (PackageIDs listos) |
| 4 | Error del SAT |
| 5 | Rechazada |

### Endpoints (ver `sat_descarga/config.py`)

```
autenticacion:      https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/Autenticacion/Autenticacion.svc
solicita_descarga:  https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/SolicitaDescargaService.svc
verifica_solicitud: https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/VerificaSolicitudDescargaService.svc
descarga_masiva:    https://cfdidescargamasiva.clouda.sat.gob.mx/DescargaMasivaService.svc
```

### API v1.5 — cambios confirmados (mayo 2025)

**Autenticación:** WS-Security SOAP. Namespace `http://DescargaMasivaTerceros.gob.mx`.
Devuelve WRAP token URL-encoded (`JWT%26wrap_subject%3dSERIAL`) que va en el header
`Authorization: WRAP access_token="{token}"`.

**Solicitud / Verificación / Descarga:**
- Nuevo namespace body: `http://DescargaMasivaTerceros.sat.gob.mx` (con `.sat`).
- NO hay token SOAP (se eliminó `SolicitaDescargaHeader`).
- Cada request lleva firma **xmldsig enveloped** (firmada con la FIEL).
- El elemento firmado es el **padre** de `<solicitud>` (ej. `SolicitaDescargaEmitidos`);
  la `<Signature>` se añade como **hijo de `<solicitud>`**.
- C14N **inclusiva** (`...REC-xml-c14n-20010315`), no exclusiva.
- Referencia `URI=""` + transform `enveloped-signature`.
- KeyInfo: `X509IssuerSerial` (issuer RFC4514 + serial decimal) + `X509Certificate`.

### Detalles descubiertos en pruebas reales (marzo 2026)

- `EstadoComprobante` usa texto: `"Vigente"`, `"Cancelado"`, `"Todos"` (no numérico) y
  debe ir **primero** en el orden de atributos.
- Recibidos requiere `RfcReceptor` explícito (= RFC del solicitante), sino error 301.
- Recibidos + CFDI solo acepta `"Vigente"` (cancelados son rechazados).
- SOAPAction de descarga: `IDescargaMasivaTercerosService/Descargar`.
- Elemento de descarga: `PeticionDescargaMasivaTercerosEntrada` (con "s" en "Terceros").
- `IdsPaquetes`: cada paquete es un `<IdsPaquetes>` separado, no hijos de un contenedor.
- "Solicitudes agotadas de por vida" (CodEstatus=5002): el SAT limita por rango exacto
  de fechas+segundos; variar los segundos genera una solicitud nueva.
- Respuesta de descarga: el `<Paquete>` (ZIP Base64) está en
  `<RespuestaDescargaMasivaTercerosSalida>`.

## Portal CIEC (scraping, sin FIEL) — `sat_descarga/ciec.py`

Para contribuyentes sin e-firma. Playwright headful: el usuario resuelve el captcha en
el browser; el resto es automático. Portal `portalcfdi.facturaelectronica.sat.gob.mx`.

- **Login:** pre-llena RFC + contraseña; espera el redirect a portalcfdi (cfdiau → SSO).
- **Radio "Fecha":** requiere **click NATIVO** (`page.click`); setear `.checked` + invocar
  `__doPostBack` por JS NO basta (el server re-renderiza con los campos disabled).
- **Emitidos:** rango de fechas; el input de fecha es disabled-por-diseño (date-picker),
  se fuerza por JS. **Recibidos:** filtra un día a la vez, se itera día por día.
- **Render AJAX:** la búsqueda usa UpdatePanel; hay que esperar a que el spinner
  `UpdateProgress1` se oculte y aparezcan filas (`networkidle` da falsos 0).
- **Descarga:** cada fila trae `RecuperaCfdi.aspx?Datos=<token>` (devuelve el XML como
  adjunto). La paginación es client-side (todas las filas en el DOM, máx 500/consulta).
- **Cuota diaria:** el portal limita descargas (`hfDescarga` = CuotaParcial/CuotaCompleta);
  el cliente se detiene tras 3 fallos seguidos.
