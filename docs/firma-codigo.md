# Firma de código — Windows (Authenticode) y macOS

Estado a **2026-06-11**: decisión tomada y trámites EN CURSO.

| Frente | Decisión | Estado |
|---|---|---|
| Windows | **IV Code Signing de SSL.com** ($129/año) + **eSigner Tier 1 anual** ($180/año, 240 firmas, 30 días gratis) | Comprado; validación individual en curso (3-5 días: ID + llamada) |
| macOS | **Apple Developer Program Individual** ($99/año) | Enrollment iniciado (app Apple Developer; ≤48 h) |
| Pipeline CI | eSigner CodeSignTool en `release.yml` + hook `desktop/scripts/esigner-sign.js` | **Listo y auto-activable por secrets** |

El certificado mostrará el **nombre personal** del titular (persona física —
decisión consciente: sin papeleo de entidad; OV/EV quedan como upgrade futuro
si se constituye el negocio).

## Por qué importa (más allá de SmartScreen)

1. **SmartScreen**: sin firma, el instalador muestra "editor desconocido" y el
   usuario tiene que hacer clic en "Más información → Ejecutar de todas formas".
   Deal-breaker para el público contable.
2. **Arranque y navegación** (confirmado en QA de v1.1.0, 2026-06-10): los
   binarios sin firma disparan el escaneo profundo de Windows Defender en el
   primer acceso a cada archivo — no solo el arranque (30-60 s del
   StartupSplash) sino también **la primera navegación a cada página**
   (~1-2 min sin poder abrir los procesadores; requests en 200 OK y consola
   limpia — todo funciona, solo que Defender escanea cada chunk en frío).
   Firmar `sat-agent.exe` Y los binarios del shell reduce ese escaneo.
3. **electron-updater**: las actualizaciones verifican la firma del publisher;
   sin firma no hay cadena de confianza entre versiones.

## Decisiones tomadas (2026-06-10/11) y por qué

- **Azure Trusted Signing (hoy "Azure Artifact Signing"): DESCARTADO.** Public
  Trust solo acepta organizaciones de USA/Canadá/UE/UK e individuos de
  USA/Canadá (onboarding de individuos además pausado) — **México no es
  elegible**. Era la opción preferida por costo (~$10/mes) pero no aplica.
- **EV: DESCARTADO por costo/beneficio.** eSigner EV Tier 1 son $100/mes y sus
  10 firmas/mes no alcanzan un release semanal (~4-6 firmas por release).
  Además desde 2024 Microsoft ya no documenta reputación SmartScreen
  inmediata ni para EV. No firmamos drivers de kernel (único caso donde EV es
  obligatorio).
- **IV (Individual Validated) + eSigner: ELEGIDO.** ~$309 USD el primer año.
  Mismo efecto sobre Defender y "editor desconocido"; la reputación
  SmartScreen se construye con descargas las primeras 2-4 semanas (la
  reputación es del certificado, así que releases posteriores nacen limpios).
- **1 año, no multi-año**: desde marzo 2026 la norma CA/B Forum limita los
  certs a 458 días — el "descuento multi-año" es cobertura prepagada con
  re-emisiones; a 1 año conservamos flexibilidad de CA.
- ⚠️ **La vía `WIN_CSC_LINK` (PFX en base64) NO funciona** con ningún cert
  moderno (norma 2023: la llave vive en token FIPS o HSM, nunca en un `.pfx`
  exportable). Por eso todo va por eSigner (cloud HSM de SSL.com).

## Qué ya está listo en el repo (auto-activable por secrets)

- **`release.yml`**:
  - Step "Setup CodeSignTool" — descarga el CLI de SSL.com y exporta
    `CODE_SIGN_TOOL_PATH`. Se salta si no hay `ES_USERNAME`.
  - Step "Firmar sat-agent.exe (eSigner)" — corre entre PyInstaller y
    electron-builder; verifica la firma con `Get-AuthenticodeSignature`
    (CodeSignTool no siempre propaga exit codes).
  - Step "Verificar firmas" — agente + instalador; falla el release si algún
    binario quedó sin firma válida.
- **`desktop/scripts/esigner-sign.js`** — hook de `win.signtoolOptions.sign`:
  electron-builder lo invoca por cada binario (TodoConta.exe, uninstaller,
  instalador NSIS). Sin credenciales en el entorno se salta solo (builds
  locales/QA sin firma, como siempre).
- **`desktop/electron-builder.yml`** — `signingHashAlgorithms: ['sha256']`
  (el default sha1+sha256 invocaría el hook DOBLE y cada firma consume cuota).
  `forceCodeSigning` sigue apagado a propósito: lo protege el step de CI.

### Consumo de cuota eSigner (Tier 1 = 240 firmas/año)

Por release: sat-agent.exe + TodoConta.exe + uninstaller + instalador ≈ **4-5
firmas**. Release semanal ≈ 200-260/año — justo en el tier; las no usadas se
acumulan y las extra cuestan $0.25-1 c/u. Si el volumen crece (releases
multi-arch de Windows, p. ej.), evaluar Tier 2.

## Checklist cuando pase la validación de SSL.com

1. En SSL.com: activar **eSigner** para el certificado emitido (enrolar).
2. En eSigner: configurar **automated signing** → genera el **TOTP secret**;
   anotar el **Credential ID** del cert. ⚠️ Si está activo el *malware
   blocker* de eSigner, deshabilitarlo para firma automatizada (bloquea la
   firma desde CI).
3. Agregar los 4 secrets al repo (Settings → Secrets and variables → Actions):
   `ES_USERNAME`, `ES_PASSWORD`, `CREDENTIAL_ID`, `ES_TOTP_SECRET`.
   **El humano los agrega directo en GitHub; nunca pasan por chats/archivos.**
4. En `desktop/electron-builder.yml`: actualizar **`publisherName` al CN
   exacto del certificado** (con IV es el nombre personal, no "TodoConta") —
   electron-updater valida la firma de cada update contra ese nombre; si no
   coincide, el auto-update rechaza instaladores firmados.
5. Correr el workflow manual (`workflow_dispatch`) y QA en una VM Windows
   limpia: sin aviso de "editor desconocido", `Get-AuthenticodeSignature` en
   Valid, y **medir el primer arranque + primera navegación** (deben bajar
   drásticamente vs. los 1-2 min actuales).
6. Los primeros días de descargas construyen la reputación SmartScreen; si un
   usuario reporta el aviso azul la primera semana, es esperado y temporal.

## macOS — DMG firmado y notarizado

Prerequisito: **Apple Developer Program Individual** ($99 USD/año) →
certificado **"Developer ID Application"**. A diferencia de Windows, Apple SÍ
permite exportar la llave como `.p12` — la vía `CSC_LINK` de electron-builder
funciona. **Enrollment iniciado 2026-06-11** (vía app Apple Developer:
verificación de identidad con INE/pasaporte; aprobación ≤48 h).

El CI ya construye DMG **por arquitectura** (job `release-macos` en
`release.yml`: `macos-13` → x64, `macos-latest` → arm64, porque PyInstaller no
cross-compila el agente). Sin secrets, los DMG salen **sin firmar** — sirven
para QA con clic-derecho → Abrir.

### Checklist al tener la cuenta de Apple

1. Crear el cert *Developer ID Application* en developer.apple.com, exportarlo
   de Keychain como `.p12` con contraseña.
2. Generar una **app-specific password** en appleid.apple.com (notarización).
3. Secrets del repo: `MAC_CSC_LINK` (`base64 < cert.p12`),
   `MAC_CSC_KEY_PASSWORD`, `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`,
   `APPLE_TEAM_ID`.
4. En `desktop/electron-builder.yml` descomentar `notarize: true` (la config
   de `hardenedRuntime` + entitlements ya está activa; sin identidad no estorba).
5. **Validar en el primer build firmado** que la notarización acepte los
   binarios del agente PyInstaller en `Contents/Resources/agent/`. Si los
   rechaza por falta de firma, agregar `mac.binaries` o un hook `afterSign`
   con `codesign --force --options runtime` recursivo (nota en el yml).
6. QA: `spctl -a -vv TodoConta.app` (aceptado), `xcrun stapler validate` sobre
   el DMG, e instalar en un Mac limpio: abre sin advertencia de Gatekeeper.

### Bonus conocido

Firmar el agente PyInstaller en macOS **elimina el cuelgue de
`keyring.get_password()`** que hoy obliga a mover `empresas.json` antes del
smoke local (ver memoria del proyecto): el Keychain deja de bloquear binarios
sin firma.

### Pendiente (no bloquea)

`electron-updater` para macOS: cada arquitectura genera su `latest-mac.yml` y
el último en subir pisa al otro. Unificar ese metadata cuando se active el
auto-update en Mac.
