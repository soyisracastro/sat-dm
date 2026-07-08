# Renovación de e.firma y solicitud de CSD (módulo `certifica/`)

Genera **en local** los mismos archivos que la app oficial **Certifica** (antes
SOLCEDI) del SAT, sin depender de esa app Java ni de ningún servicio del SAT para
construirlos. Reimplementación en Python puro (solo `cryptography`), **portada de
[`satcfdi.certifica`](https://github.com/SAT-CFDI/python-satcfdi) (licencia MIT)**
y adaptada a la `FIEL` de este proyecto (`core/fiel.py`).

## Los tres artefactos

| Archivo | Trámite | Qué es | Firma con e.firma vigente |
|---|---|---|---|
| `.req` | Generación de e.firma **nueva** | PKCS#10 auto-firmado con la llave **nueva** | — (no hay e.firma previa) |
| `.ren` | **Renovación** de e.firma | El PKCS#10 anterior envuelto en un **PKCS#7/CMS** | **sí** |
| `.sdg` | Solicitud de **CSD** (sello digital) | **ZIP** de PKCS#10 tipo SELLO (uno por sucursal) envuelto en CMS | **sí** |

Espina común: se genera un **par RSA-2048 nuevo**, se cifra el `.key`, y se arma un
**PKCS#10** (subject con OIDs del SAT: `2.5.4.45`=RFC, `2.5.4.5`=CURP,
`emailAddress`, y para CSD `CN`/`O`=razón social + `OU`=sucursal; atributo
`challengePassword`). Para `.ren` y `.sdg` ese PKCS#10 se firma **por fuera** con
la e.firma **vigente** (CMS SignedData con `signingTime` y el certificado vigente
incrustado). Todo con **SHA-1**, igual que Certifica.

## CLI

```bash
# Renovación (lo más común): genera Renovacion_FIEL_<RFC>_<fecha>.ren + .key nuevo
sat-dm renovar fiel --cer vigente.cer --key vigente.key            # persona física
sat-dm renovar fiel --cer ... --key ... --rfc-moral XAX010101000   # persona moral (con rep. legal)

# Solicitud de Certificado de Sello Digital
sat-dm solicitar csd --cer ... --key ... --sucursal "Matriz Centro"

# Generación de e.firma nueva (sin e.firma previa)
sat-dm generar fiel --rfc XAXX010101000 --curp XAXX010101HDFXXX01 --correo yo@correo.com
```

Las contraseñas (de la e.firma vigente y de la nueva `.key`) se piden ocultas si no
se pasan por flag. `--salida` elige el directorio de salida (default: actual).

## API pública

```python
from sat_descarga import (
    FIEL,
    generar_requerimiento_fiel,     # .req  (rfc, curp, correo, password, salida_dir)
    generar_renovacion_fiel,        # .ren  (fiel, correo, password, salida_dir)
    generar_renovacion_fiel_moral,  # .ren  (fiel, rfc_moral, correo, password, salida_dir)
    generar_solicitud_csd,          # .sdg  (fiel, sucursal, password, salida_dir)
)

fiel = FIEL("vigente.cer", "vigente.key", "contraseña")
rutas = generar_renovacion_fiel(fiel, correo=None, password="NuevaClave", salida_dir="out/")
# {"key": Path(...), "ren": Path(...)}
```

## Flujo completo (el envío es aparte)

Este módulo **solo genera los archivos**, igual que Certifica. El envío al SAT es
manual/scraping:

1. `sat-dm renovar fiel ...` → produce `.ren` + `.key` nuevo (guarda bien la nueva
   `.key` y su contraseña).
2. Entra a **CertiSAT Web** (https://www.sat.gob.mx → e.firma) con la e.firma
   **vigente** → **«Renovación del certificado»** → sube el `.ren` → **Renovar**.
3. Anota el **número de operación**, consulta **Seguimiento** y guarda el acuse.
4. Descarga el **`.cer` nuevo** en **«Recuperación de certificados»** y guárdalo
   junto a la `.key` nueva.

## Envío automatizado (CSD) — `portal/csd.py`

El envío del `.sdg` a CertiSAT Web ya está automatizado (login e.firma sin captcha,
headless), probado contra el SAT real:

```bash
# Generar y enviar en un paso (recupera el CSD si ya se publicó):
sat-dm solicitar csd --cer ... --key ... --sucursal "Matriz" --enviar
# Subir un .sdg ya generado:
sat-dm enviar csd --cer ... --key ... --sdg archivo.sdg --key-nueva sello.key
# Descargar DESPUÉS el CSD emitido (patrón asíncrono, ver abajo):
sat-dm recuperar csd --cer ... --key ... --key-nueva sello.key
```

API: `enviar_solicitud_csd_fiel(...)` y `recuperar_ultimo_csd_fiel(...)` en
`sat_descarga.portal.csd`. Flujo: login NIDP e.firma (`iniciar_sesion_fiel`) →
`requerimiento.do` (subir `.sdg`) → número de operación → Seguimiento (acuse) →
Recuperación (descarga del `.cer`).

Detalles no obvios aprendidos en la corrida real (importantes para no romperlo):

- **Predicado de login por HOST, no por substring**: el host `aplicacionesc.mat.sat.gob.mx`
  aparece dentro del `target=` de la URL de login → `"host" in url` da falso positivo
  y "aterriza" sin entrar. Hay que exigir que el host REAL (antes del `?`) sea ese.
- **`/nidp/app` intermitente**: el NIDP a veces se atora en `loginc.../nidp/app` en vez
  de aterrizar en CertiSAT → `_login` reintenta (cada intento re-entra fresco).
- **El `.cer` no está disponible de inmediato** (tarda minutos en publicarse) → la
  recuperación reintenta y **verifica que el CSD empareje con la `.key` nueva** para no
  bajar un certificado viejo. En la UI conviene el patrón asíncrono: el envío devuelve
  el número de operación al instante y la descarga del `.cer` es un paso aparte
  («bajar después» → `recuperar_ultimo_csd_fiel`).
- **Descarga del `.cer` por HTTP directo** (`requests`, `verify=False`): `rdc.sat.gob.mx`
  es público y su TLS lo acepta requests/curl; el navegador lo trata como descarga
  (content-type `x-x509-ca-cert`). Fallback: captura de la descarga con el navegador.

### Envío automatizado (RENOVACIÓN) — `portal/renovacion.py`

La renovación (`.ren`) reusa TODA la mecánica del CSD (`CSDPortalClient`): solo
cambian el menú (`renovacion.do?menu=renovacion`), el input (`#txtFileRen`, name
`renovacion`) y el acuse (`Acuse_renovacion.pdf`). El botón es el mismo
`input[name="enviar"]` (value "Renovar").

```bash
sat-dm renovar fiel --cer ... --key ... --enviar   # genera y sube el .ren (pide confirmación)
sat-dm enviar ren   --cer ... --key ... --ren archivo.ren
sat-dm recuperar ren --cer ... --key ... --key-nueva nueva.key
```

API: `enviar_renovacion_fiel(...)` / `recuperar_renovacion_fiel(...)`.

⚠️ **Ventana post-renovación (confirmada en vivo):** al renovar, la e.firma anterior
queda **revocada de inmediato** y el SAT **no reconoce la nueva para login hasta
HORAS después** (propagación; el servidor emisor va en UTC). O sea, justo después de
renovar **ni la vieja ni la nueva** sirven para autenticar en el portal. La UI debe
avisar de esto. La renovación NO se puede re-testear libremente (cada envío sustituye
la e.firma única) → se valida por analogía con el CSD (código idéntico) + el
emparejamiento offline del `.cer` renovado con la `.key` generada.

Detalle del portal en `docs/path-renovacion-efirma.md` (no commiteado: PII) y la
*Guía ... CertiSAT WEB* del SAT.

## Verificación

`tests/test_certifica.py` genera los tres artefactos con la e.firma de prueba y los
verifica **de forma independiente**:

- PKCS#10 interno: auto-firma SHA-1 válida (comprobada a mano — `is_signature_valid`
  devuelve `False` para SHA-1 por política de `cryptography` reciente, pero la firma
  **sí** es válida, como confirma `openssl req -verify`), OIDs y `challengePassword`.
- CMS `.ren`/`.sdg`: certificado vigente incrustado y, con `openssl` en el PATH,
  `openssl cms -verify` confirma la firma con la e.firma vigente; se valida el
  contenido encapsulado (PKCS#10 o ZIP+PKCS#10 SELLO).
- El nuevo `.key` abre con su contraseña.

## Notas / decisiones

- **SHA-1**: este build de Certifica firma todo con SHA-1 y el SAT lo sigue
  aceptando (satcfdi está activo en producción). **Validar contra el portal real**
  antes de anunciarlo; si algún día el SAT exige SHA-256, subir el hash del PKCS#10
  y del CMS.
- **`.key` con AES-256** (`BestAvailableEncryption`) en lugar del 3DES de Certifica:
  el `.key` **nunca** se envía al SAT (solo lo guarda el usuario) y las herramientas
  modernas leen PKCS#8/AES sin problema. Solo cambian esos bytes, no la solicitud.
- **No byte-idéntico a Certifica**: el CMS puede diferir en el framing (DER vs BER)
  sin afectar la validez; el SAT acepta el DER. La equivalencia funcional está
  verificada por `satcfdi` contra archivos reales de Certifica.
- **Trámite FIEL-only**: renovación y CSD-vía-Certifica requieren la e.firma; no hay
  variante CIEC (excepción a la convención de exponer ambos canales).
- **Atribución**: incluir el texto de la licencia MIT de `satcfdi` antes de publicar.

## Estado

- ✅ Generación de `.req`, `.ren` (física y moral) y `.sdg`, verificada con
  `cryptography` + `openssl` sobre e.firma de prueba.
- ✅ **CSD probado de punta a punta contra el SAT real**: `.sdg` generado → aceptado
  (número de operación) → CSD emitido → recuperado y **empareja con la `.key`** generada.
- ✅ Envío automatizado del `.sdg` en `portal/csd.py` (login e.firma headless) +
  recuperación independiente (`recuperar csd`).
- ⏳ Automatizar la **renovación** (`.ren`) en `portal/` (mismo login; siguiente paso).
