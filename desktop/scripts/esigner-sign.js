/**
 * Hook de firma custom para electron-builder (win.signtoolOptions.sign).
 *
 * Firma cada binario que electron-builder firmaría con signtool (TodoConta.exe,
 * el uninstaller y el instalador NSIS) usando CodeSignTool de SSL.com eSigner
 * (IV Code Signing en cloud HSM — ver docs/infra/firma-codigo.md).
 *
 * Sin credenciales eSigner en el entorno, se salta solo: los builds locales y
 * de QA salen sin firma, igual que siempre. Por eso `forceCodeSigning` sigue
 * apagado — la protección del release la da el step "Verificar firmas" del CI.
 *
 * Env requerida para firmar (la setea release.yml):
 *   ES_USERNAME / ES_PASSWORD / CREDENTIAL_ID / ES_TOTP_SECRET
 *   CODE_SIGN_TOOL_PATH — carpeta donde vive CodeSignTool.bat
 *
 * Nota de cuota: cada invocación consume 1 firma de la suscripción eSigner
 * (Tier 1 = 240/año). `signingHashAlgorithms: ['sha256']` en electron-builder.yml
 * evita que el hook se llame doble (sha1+sha256) por archivo.
 */

'use strict';

const { execSync } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');

exports.default = async function esignerSign(configuration) {
  const archivo = configuration.path;
  const { ES_USERNAME, ES_PASSWORD, CREDENTIAL_ID, ES_TOTP_SECRET, CODE_SIGN_TOOL_PATH } =
    process.env;

  if (!ES_USERNAME || !ES_PASSWORD || !CREDENTIAL_ID || !ES_TOTP_SECRET) {
    console.log(
      `  [esigner] sin credenciales eSigner — ${path.basename(archivo)} queda SIN firmar (build dev/QA)`,
    );
    return;
  }
  if (!CODE_SIGN_TOOL_PATH) {
    throw new Error(
      '[esigner] Hay credenciales eSigner pero falta CODE_SIGN_TOOL_PATH (lo setea el step "Setup CodeSignTool" de release.yml).',
    );
  }
  const bat = path.join(CODE_SIGN_TOOL_PATH, 'CodeSignTool.bat');
  if (!fs.existsSync(bat)) {
    throw new Error(`[esigner] No existe ${bat}`);
  }

  console.log(`  [esigner] firmando ${path.basename(archivo)}…`);
  // CodeSignTool.bat referencia sus jars con paths relativos → cwd a su carpeta.
  // execSync con string (no execFile): los .bat requieren shell en Windows.
  execSync(
    [
      `"${bat}"`,
      'sign',
      `-username="${ES_USERNAME}"`,
      `-password="${ES_PASSWORD}"`,
      `-credential_id="${CREDENTIAL_ID}"`,
      `-totp_secret="${ES_TOTP_SECRET}"`,
      `-input_file_path="${archivo}"`,
      '-override=true',
    ].join(' '),
    { cwd: CODE_SIGN_TOOL_PATH, stdio: 'inherit' },
  );
};
