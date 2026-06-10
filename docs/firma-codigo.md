# Firma de código — Windows (Authenticode)

Estado: **pipeline listo, certificado pendiente** (financiación de contadores
fundadores en curso). El CI ya trae los steps de firma con guards: se activan
solos cuando existan los secrets; mientras tanto son no-op y el build sale sin
firma, como hoy.

## Por qué importa (más allá de SmartScreen)

1. **SmartScreen**: sin firma, el instalador muestra "editor desconocido" y el
   usuario tiene que hacer clic en "Más información → Ejecutar de todas formas".
   Deal-breaker para el público contable.
2. **Arranque**: el `sat-agent.exe` (PyInstaller, ~50 archivos) sin firma
   dispara el escaneo profundo de Windows Defender en el primer arranque —
   los 30-60 s de espera que hoy cubre el StartupSplash. **Firmar el binario
   del agente reduce ese escaneo**, no solo el del instalador.
3. **electron-updater**: las actualizaciones diferenciales verifican la firma
   del publisher; sin firma no hay cadena de confianza entre versiones.

## ⚠️ Lo que cambió en 2023 (leer antes de comprar)

Desde junio 2023 (norma CA/Browser Forum), los certificados OV y EV **ya no se
entregan como archivo `.pfx`**: la llave privada debe vivir en hardware
certificado (token USB FIPS) o en un HSM en la nube. Consecuencia directa:

> La vía `WIN_CSC_LINK` (PFX en base64) que electron-builder documenta y que
> está comentada en `release.yml` **NO funciona** con un cert moderno. No
> comprar un EV esperando exportar un `.pfx` para GitHub Actions.

## Opciones reales para firmar en GitHub Actions

| | **Azure Trusted Signing** (recomendado evaluar 1º) | **EV tradicional + firma en nube del CA** |
|---|---|---|
| Costo | ~$9.99 USD/mes | ~$300-500 USD/año + costo por firma del servicio (eSigner/KeyLocker) |
| SmartScreen | Reputación inmediata (como EV) | Reputación inmediata |
| CI | Nativo: `azure/trusted-signing-action` + `win.azureSignOptions` de electron-builder ≥25 | Vía CLI del CA (eSigner CodeSignTool, smctl de DigiCert) |
| Identidad | Validación de negocio por Microsoft; verificar elegibilidad (entidad con historial verificable; hay soporte para individuos en algunas regiones) | Validación EV clásica del CA |
| Lock-in | Cuenta Azure (solo el servicio de firma; no hay que migrar nada más) | CA elegido |
| Alternativa con token físico | n/a | Solo con runner self-hosted con el USB conectado (no recomendado) |

## Qué ya está listo en el repo

- **`release.yml`**: job con `env` de los secrets de Azure; si `AZURE_TENANT_ID`
  está vacío, los steps de firma/verificación se saltan.
  - Step "Firmar sat-agent.exe" — corre entre PyInstaller y electron-builder.
  - Step "Verificar firmas" — `Get-AuthenticodeSignature` sobre el agente y el
    instalador; falla el build si la firma no es válida.
- **`electron-builder.yml`**: bloque `azureSignOptions` documentado (comentado).

## Checklist al adquirir (opción Azure Trusted Signing)

1. Crear el recurso *Trusted Signing* en Azure + *certificate profile* (public
   trust) con la identidad validada → `TodoConta` como publisher.
2. Crear un *App registration* (service principal) con rol
   `Trusted Signing Certificate Profile Signer`.
3. Agregar secrets al repo: `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`,
   `AZURE_CLIENT_SECRET`, `AZURE_SIGNING_ENDPOINT` (p. ej.
   `https://eus.codesigning.azure.net`), `AZURE_SIGNING_ACCOUNT`,
   `AZURE_CERT_PROFILE`.
4. En `desktop/electron-builder.yml`: descomentar el bloque `azureSignOptions`
   y poner `forceCodeSigning: true` (el build de release falla si falta firma —
   evita publicar un .exe sin firmar por accidente).
5. Correr el workflow manual (workflow_dispatch) y QA en una VM Windows limpia:
   sin aviso de SmartScreen + medir el primer arranque (debe bajar vs. hoy).

## Checklist alternativa (EV + eSigner/KeyLocker)

1. Comprar EV con opción de firma en nube (SSL.com eSigner o DigiCert KeyLocker).
2. Reemplazar el step de Azure en `release.yml` por el CLI del CA (p. ej.
   `CodeSignTool sign` con `ES_USERNAME/ES_PASSWORD/CREDENTIAL_ID/ES_TOTP_SECRET`).
3. Para electron-builder, usar `win.signtoolOptions.sign` (hook custom) que
   invoque ese CLI por cada binario.
4. Mismos pasos 4-5 de arriba.

## macOS

La firma + notarización de macOS va en su propio track (Developer ID +
notarytool); ver el PR del instalador macOS. Bonus conocido: firmar el agente
PyInstaller en macOS elimina el cuelgue de `keyring.get_password()` con
binarios sin firma.
