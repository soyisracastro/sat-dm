'use client';

import { useEffect, useState } from 'react';

import { Bell } from '@/components/notifications/bell';
import { FounderBadge } from '@/components/auth/founder-badge';
import { WindowControls } from '@/components/layout/window-controls';

/**
 * Franja superior de la ventana. En Electron es una región arrastrable
 * (`-webkit-app-region: drag`) y el chrome depende del SO:
 * - macOS (`titleBarStyle: hiddenInset`): reserva a la izquierda el espacio de
 *   los semáforos nativos.
 * - Windows (`titleBarStyle: hidden`): sin barra nativa — la app dibuja sus
 *   propios min/max/cerrar (`WindowControls`) pegados al borde derecho.
 * En el navegador (dev) es solo una franja normal.
 *
 * La campana y el badge van en su propio contenedor `no-drag` (la regla global
 * de globals.css cubre los popovers flotantes).
 */
function detectar(): { desktop: boolean; mac: boolean; win: boolean } {
  if (typeof window === 'undefined') return { desktop: false, mac: false, win: false };
  const w = window as unknown as {
    satAgent?: { isDesktop?: boolean };
    satDesktop?: { platform?: string };
  };
  const desktop = !!w.satAgent?.isDesktop;
  // El preload expone la plataforma real; user-agent solo como fallback
  // (preloads viejos / navegador dev).
  const platform = w.satDesktop?.platform;
  if (platform) {
    return { desktop, mac: platform === 'darwin', win: platform === 'win32' };
  }
  const ua = navigator.platform || navigator.userAgent || '';
  return { desktop, mac: /Mac/i.test(ua), win: /Win/i.test(ua) };
}

export function Titlebar() {
  const [{ desktop, mac, win }, set] = useState({
    desktop: false,
    mac: false,
    win: false,
  });

  useEffect(() => {
    set(detectar());
  }, []);

  const conControles = desktop && win;
  const style: React.CSSProperties & { WebkitAppRegion?: string } = {
    paddingLeft: desktop && mac ? 78 : 14,
    // En Windows los controles van pegados al borde (sin padding).
    paddingRight: conControles ? 0 : 6,
  };
  if (desktop) style.WebkitAppRegion = 'drag';

  return (
    <div
      className="flex h-9 shrink-0 select-none items-center gap-2 border-b bg-card"
      style={style}
    >
      {/* La marca vive en el sidebar; la franja queda como zona de drag. */}
      <div
        className="ml-auto flex h-full items-center gap-2"
        style={desktop ? { WebkitAppRegion: 'no-drag' } as React.CSSProperties & { WebkitAppRegion?: string } : undefined}
      >
        <FounderBadge />
        <Bell />
        {conControles && <WindowControls />}
      </div>
    </div>
  );
}
