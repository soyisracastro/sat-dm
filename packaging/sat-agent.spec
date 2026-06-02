# -*- mode: python ; coding: utf-8 -*-
"""
Spec de PyInstaller para empaquetar el agente FastAPI como `sat-agent.exe`
distribuible junto al shell Electron.

Uso:
    pyinstaller packaging/sat-agent.spec --noconfirm --clean

Salida:
    packaging/dist/sat-agent/sat-agent[.exe]     # binario
    packaging/dist/sat-agent/*.dll/*.pyd         # dependencias dinámicas
    packaging/build/                              # artefactos intermedios

El binario se invoca con:
    sat-agent.exe --port <N>

Decisiones:
- `onedir` (no `onefile`): un .exe + dlls en carpeta. Razones:
    1. `onefile` extrae a %TEMP% en cada arranque (1-3s extra de latencia).
    2. Antivirus marcan más frecuentemente los `onefile`.
    3. Patches/updates más fáciles en carpeta (electron-updater reemplaza la
       carpeta completa).
- Playwright SÍ está incluido (sus driver/binding); el navegador Chromium se
  descarga en runtime (ver `sat_descarga/portal/setup.py`).
- Pesados excluidos: pillow, tkinter, matplotlib, IPython.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Path al root del repo: el spec vive en `packaging/`, así que ..  es la raíz.
REPO_ROOT = Path(SPECPATH).parent  # type: ignore[name-defined]
ENTRY = REPO_ROOT / "sat_descarga" / "api" / "__main__.py"

# -----------------------------------------------------------------------------
# Datas (archivos no-Python que el agente necesita en runtime)
# -----------------------------------------------------------------------------

datas: list[tuple[str, str]] = []

# Migraciones SQL del procesador (leídas con Path(__file__).parent / "migrations").
migrations_dir = REPO_ROOT / "sat_descarga" / "procesador" / "migrations"
if migrations_dir.exists():
    for sql in migrations_dir.glob("*.sql"):
        datas.append((str(sql), "sat_descarga/procesador/migrations"))
    readme = migrations_dir / "README.md"
    if readme.exists():
        datas.append((str(readme), "sat_descarga/procesador/migrations"))

# Driver de Playwright (node + cli + package.json). Sin esto sync_playwright()
# revienta porque no encuentra el driver embebido. Chromium NO se incluye —
# se descarga en runtime (ver portal/setup.py).
datas.extend(collect_data_files("playwright", include_py_files=False))


# -----------------------------------------------------------------------------
# Hidden imports (paquetes detectados como dinámicos por PyInstaller)
# -----------------------------------------------------------------------------

hiddenimports: list[str] = [
    # uvicorn — loops y protocols se cargan por nombre
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    # pydantic
    "pydantic.deprecated.decorator",
    "pydantic_core",
    # lxml (Windows pierde imports dinámicos de xpath)
    "lxml._elementpath",
    "lxml.etree",
    # email (FastAPI multipart upload)
    "email.mime.multipart",
    "email.mime.text",
    "email.mime.base",
    # python-multipart (uploads)
    "multipart",
    # playwright (driver runtime)
    "playwright.sync_api",
    "playwright._impl._driver",
    "playwright._impl._connection",
    "playwright._impl._helper",
    "playwright._impl._api_types",
    # Internos del agente (importados dinámicamente desde server.py)
    "sat_descarga.cli.config_store",
    "sat_descarga.cli.empresas",
    "sat_descarga.procesador",
    "sat_descarga.procesador.db",
    "sat_descarga.procesador.cfdi_parser",
    "sat_descarga.procesador.exportar",
    "sat_descarga.procesador.exportar_pagos",
    "sat_descarga.procesador.exportar_nomina",
    "sat_descarga.procesador.reportes_cfdi",
    "sat_descarga.procesador.reportes_pagos",
    "sat_descarga.procesador.reportes_nomina",
    "sat_descarga.portal.setup",
    "sat_descarga.portal.cfdi",
    "sat_descarga.portal.constancia",
    "sat_descarga.portal.opinion",
    "sat_descarga.portal.login",
]

# Recolectar todos los submódulos de uvicorn y playwright (cinturón + tirantes).
hiddenimports.extend(collect_submodules("uvicorn"))
hiddenimports.extend(collect_submodules("playwright"))

# -----------------------------------------------------------------------------
# Excludes (paquetes que NO queremos en el bundle — ahorro de tamaño)
# -----------------------------------------------------------------------------

excludes: list[str] = [
    "pillow",
    "PIL",
    "tkinter",
    "matplotlib",
    "IPython",
    "jedi",
    "pytest",
    "setuptools",
    # supabase: solo lo usa `hosted.py` (Railway/cloud), no el agente local.
    "supabase",
    "gotrue",
    "postgrest",
    "storage3",
    "realtime",
    # dotenv: idem
    "python_dotenv",
    "dotenv",
]


# -----------------------------------------------------------------------------
# Analysis + EXE + COLLECT
# -----------------------------------------------------------------------------

a = Analysis(  # noqa: F821 — PyInstaller inyecta esto
    [str(ENTRY)],
    pathex=[str(REPO_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="sat-agent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,         # UPX a veces dispara antivirus; desactivado.
    console=True,      # El agente loguea a stderr; consola visible solo en dev.
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="sat-agent",
)
