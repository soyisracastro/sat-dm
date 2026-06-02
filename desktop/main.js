'use strict';
/*
 * Proceso principal de Electron (TodoConta Desktop).
 *
 * Responsabilidades:
 *   1. Levantar el AGENTE Python (FastAPI) en un puerto efímero local.
 *   2. Esperar a que responda /health.
 *   3. Abrir la ventana y cargar el renderer (ui/), inyectándole el base URL del
 *      agente vía el preload (window.satAgent.baseUrl).
 *   4. Cerrar el agente al salir.
 *
 * Dev:  el agente se levanta con `uv run uvicorn ...` desde la raíz del repo, y el
 *       renderer se sirve con `next dev` (puerto 3001). En producción el agente será
 *       el binario congelado (PyInstaller) y el renderer un export estático (se
 *       ajustará al empaquetar con electron-builder).
 *
 * Variables de entorno (overrides):
 *   SAT_AGENT_URL      Si ya tienes el agente corriendo, úsalo (no se spawnea).
 *   SAT_AGENT_CMD      Comando para levantar el agente (usa el puerto en SAT_AGENT_PORT).
 *   SAT_RENDERER_URL   URL del renderer (default http://localhost:3001).
 */

const { app, BrowserWindow, Notification, nativeImage, shell, dialog, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const net = require('net');
const http = require('http');

const REPO_ROOT = path.resolve(__dirname, '..');
const APP_ICON = path.join(__dirname, 'assets', 'icon.png');

// Nombre visible en el menú de la app de macOS (About / Hide / Quit) y en
// `app.getName()`. El tooltip del dock y el source de las notificaciones
// nativas siguen viniendo del bundle (Electron.app en dev) — eso solo
// cambia cuando empaquetemos con electron-builder. Debe llamarse antes
// de app.whenReady() para que surta efecto en el menú inicial.
app.setName('TodoConta');

// AppUserModelId: obligatorio en Windows 10/11 para que las notificaciones
// nativas aparezcan con el nombre correcto en el Action Center y se agrupen
// bien en el taskbar. DEBE setearse antes de app.whenReady() o no surte
// efecto. Mismo id que usaremos para el appId de electron-builder cuando
// empaquetemos para producción.
if (process.platform === 'win32') {
  app.setAppUserModelId('com.todoconta.satdescargamasiva');
}

let agentProc = null;
let agentUrl = null;

function getFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on('error', reject);
    srv.listen(0, '127.0.0.1', () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });
}

function waitForHealth(baseUrl, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve, reject) => {
    const attempt = () => {
      const req = http.get(`${baseUrl}/health`, (res) => {
        res.resume();
        if (res.statusCode === 200) resolve();
        else retry();
      });
      req.on('error', retry);
    };
    const retry = () => {
      if (Date.now() > deadline) {
        reject(new Error('El agente no respondió a /health a tiempo.'));
      } else {
        setTimeout(attempt, 400);
      }
    };
    attempt();
  });
}

/**
 * Resuelve [cmd, cwd] para spawnear el agente Python según el entorno.
 *
 * - Producción (empaquetado por electron-builder): usa el binario `sat-agent.exe`
 *   incluido como extraResource. `app.isPackaged === true` y el binario vive en
 *   `<resources>/agent/sat-agent.exe` (o sin .exe en macOS/Linux para dev).
 * - Override por env: SAT_AGENT_CMD permite forzar un comando arbitrario
 *   (útil para QA o builds custom). Se respeta siempre, incluso en producción.
 * - Dev (no empaquetado): default a `uv run uvicorn sat_descarga.api.server:app`
 *   desde la raíz del repo.
 */
function resolverComandoAgente(port) {
  if (process.env.SAT_AGENT_CMD) {
    return {
      cmd: process.env.SAT_AGENT_CMD.split(' '),
      cwd: process.cwd(),
    };
  }

  if (app.isPackaged) {
    const exeName = process.platform === 'win32' ? 'sat-agent.exe' : 'sat-agent';
    const agentExe = path.join(process.resourcesPath, 'agent', exeName);
    return {
      // El agente lee --port y/o $SAT_AGENT_PORT.
      cmd: [agentExe, '--port', String(port)],
      // cwd = dir del .exe para que lxml/uvicorn encuentren sus dlls relativos.
      cwd: path.dirname(agentExe),
    };
  }

  // Dev (no empaquetado).
  return {
    cmd: ['uv', 'run', 'uvicorn', 'sat_descarga.api.server:app',
          '--host', '127.0.0.1', '--port', String(port)],
    cwd: REPO_ROOT,
  };
}

/**
 * Resuelve la URL del renderer (la app Next.js) según el entorno.
 *
 * - Override por env: SAT_RENDERER_URL siempre gana (debug, builds custom).
 * - Producción: bundle estático exportado a ui/out/ → empaquetado como
 *   extraResource en `<resources>/ui/index.html` → file:// URL.
 * - Dev (no empaquetado): http://localhost:3001 donde corre `pnpm dev` del UI.
 */
function resolverRendererUrl() {
  if (process.env.SAT_RENDERER_URL) {
    return process.env.SAT_RENDERER_URL;
  }
  if (app.isPackaged) {
    const indexHtml = path.join(process.resourcesPath, 'ui', 'index.html');
    // Electron acepta file:// — pathToFileURL produce el formato correcto
    // (incluyendo escape de espacios en Windows, p. ej. "C:\Program Files").
    return require('url').pathToFileURL(indexHtml).toString();
  }
  return 'http://localhost:3001';
}

async function startAgent() {
  // Si el dev ya levantó el agente manualmente, conéctate a ese.
  if (process.env.SAT_AGENT_URL) {
    agentUrl = process.env.SAT_AGENT_URL.replace(/\/+$/, '');
    await waitForHealth(agentUrl);
    return;
  }

  const port = await getFreePort();
  agentUrl = `http://127.0.0.1:${port}`;

  const { cmd, cwd } = resolverComandoAgente(port);

  console.log('[agente] iniciando:', cmd.join(' '), '(cwd:', cwd + ')');
  agentProc = spawn(cmd[0], cmd.slice(1), {
    cwd,
    env: { ...process.env, SAT_AGENT_PORT: String(port) },
    stdio: 'inherit',
  });
  agentProc.on('error', (e) => console.error('[agente] no se pudo lanzar:', e.message));
  agentProc.on('exit', (code) => console.log('[agente] terminó (código', code + ')'));

  await waitForHealth(agentUrl);
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 1024,
    minHeight: 700,
    backgroundColor: '#F7F9FC',
    // En Windows/Linux esto pinta el ícono del taskbar/ventana; en macOS
    // el dock se setea aparte vía app.dock.setIcon (más abajo).
    icon: APP_ICON,
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      // El preload lee este arg y expone window.satAgent.baseUrl al renderer.
      additionalArguments: [`--sat-agent-url=${agentUrl || ''}`],
    },
  });

  // Links externos → navegador del SO (p. ej. el billing de la web).
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  const rendererUrl = resolverRendererUrl();
  win.loadURL(rendererUrl);
}

// Selector de carpeta nativo (lo usa Ajustes para elegir dónde guardar descargas).
ipcMain.handle('elegir-carpeta', async () => {
  const r = await dialog.showOpenDialog({
    properties: ['openDirectory', 'createDirectory'],
  });
  return r.canceled || r.filePaths.length === 0 ? null : r.filePaths[0];
});

// Notificaciones nativas del SO.
//   title: string (corto, ≤40 chars idealmente)
//   body: string (mensaje del pool de lib/notify/messages.ts)
//   urgent: boolean (si true, el SO suena; si false, silent)
// El click enfoca la ventana de la app (sale de minimizado, sube al frente).
ipcMain.handle('notify-native', (_e, payload) => {
  if (!Notification.isSupported()) return false;
  const { title, body, urgent } = payload || {};
  if (!title) return false;

  const n = new Notification({
    title: String(title),
    body: body ? String(body) : '',
    silent: !urgent,
  });
  n.on('click', () => {
    const wins = BrowserWindow.getAllWindows();
    const win = wins[0];
    if (!win) return;
    if (win.isMinimized()) win.restore();
    win.show();
    win.focus();
    win.moveTop();
    // En Windows, limpia el resaltado del taskbar después de enfocar.
    if (process.platform === 'win32') {
      try { win.flashFrame(false); } catch (_) { /* noop */ }
    }
  });
  n.show();
  return true;
});

app.whenReady().then(async () => {
  // macOS: el ícono del dock se cambia explícitamente (no lo agarra del
  // BrowserWindow). En Win/Linux ya quedó vía `icon:` en createWindow.
  if (process.platform === 'darwin' && app.dock) {
    try {
      app.dock.setIcon(nativeImage.createFromPath(APP_ICON));
    } catch (e) {
      console.warn('[icon] no se pudo setear el dock icon:', e.message);
    }
  }

  try {
    await startAgent();
  } catch (e) {
    console.error('No se pudo iniciar el agente Python:', e.message);
    // Abrimos la ventana de todos modos; el renderer mostrará "sin conexión".
  }
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('will-quit', () => {
  if (agentProc) {
    try {
      agentProc.kill();
    } catch (_) {
      /* noop */
    }
  }
});
