'use client';

import { useEffect, useState } from 'react';

import { Bell } from '@/components/notifications/bell';
import { FounderBadge } from '@/components/auth/founder-badge';

/**
 * Franja superior de la ventana. En Electron es una región arrastrable
 * (`-webkit-app-region: drag`) y, en macOS (`titleBarStyle: hiddenInset`), reserva
 * a la izquierda el espacio de los semáforos para que el contenido no se les encime.
 * En el navegador (dev) es solo una barra de marca normal.
 *
 * La campana de notificaciones va al lado derecho con su propio `no-drag`
 * (la regla global cubre el popover; el trigger lo marca el componente).
 */
function detectar(): { desktop: boolean; mac: boolean } {
  if (typeof window === 'undefined') return { desktop: false, mac: false };
  const w = window as unknown as { satAgent?: { isDesktop?: boolean } };
  const desktop = !!w.satAgent?.isDesktop;
  const ua = navigator.platform || navigator.userAgent || '';
  return { desktop, mac: /Mac/i.test(ua) };
}

export function Titlebar() {
  const [{ desktop, mac }, set] = useState({ desktop: false, mac: false });

  useEffect(() => {
    set(detectar());
  }, []);

  const style: React.CSSProperties & { WebkitAppRegion?: string } = {
    paddingLeft: desktop && mac ? 78 : 14,
    paddingRight: 6,
  };
  if (desktop) style.WebkitAppRegion = 'drag';

  return (
    <div
      className="flex h-9 shrink-0 select-none items-center gap-2 border-b bg-card"
      style={style}
    >
      <span className="text-xs font-semibold tracking-tight text-foreground">
        SAT Descarga Masiva
      </span>
      <div
        className="ml-auto flex items-center gap-2"
        style={desktop ? { WebkitAppRegion: 'no-drag' } as React.CSSProperties & { WebkitAppRegion?: string } : undefined}
      >
        <FounderBadge />
        <Bell />
      </div>
    </div>
  );
}
