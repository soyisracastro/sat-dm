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

const { app, BrowserWindow, shell, dialog, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const net = require('net');
const http = require('http');

const REPO_ROOT = path.resolve(__dirname, '..');

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

async function startAgent() {
  // Si el dev ya levantó el agente manualmente, conéctate a ese.
  if (process.env.SAT_AGENT_URL) {
    agentUrl = process.env.SAT_AGENT_URL.replace(/\/+$/, '');
    await waitForHealth(agentUrl);
    return;
  }

  const port = await getFreePort();
  agentUrl = `http://127.0.0.1:${port}`;

  const cmd = process.env.SAT_AGENT_CMD
    ? process.env.SAT_AGENT_CMD.split(' ')
    : ['uv', 'run', 'uvicorn', 'sat_descarga.api.server:app',
       '--host', '127.0.0.1', '--port', String(port)];

  console.log('[agente] iniciando:', cmd.join(' '), '(cwd:', REPO_ROOT + ')');
  agentProc = spawn(cmd[0], cmd.slice(1), {
    cwd: REPO_ROOT,
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

  const rendererUrl = process.env.SAT_RENDERER_URL || 'http://localhost:3001';
  win.loadURL(rendererUrl);
}

// Selector de carpeta nativo (lo usa Ajustes para elegir dónde guardar descargas).
ipcMain.handle('elegir-carpeta', async () => {
  const r = await dialog.showOpenDialog({
    properties: ['openDirectory', 'createDirectory'],
  });
  return r.canceled || r.filePaths.length === 0 ? null : r.filePaths[0];
});

app.whenReady().then(async () => {
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
