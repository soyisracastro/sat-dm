'use client';

import { useEffect, useState } from 'react';

import { Bell } from '@/components/notifications/bell';
import { ReportButton } from '@/components/feedback/report-button';
import { PlanBadge } from '@/components/auth/plan-badge';
import { WindowControls } from '@/components/layout/window-controls';
import { detectarPlataforma } from '@/lib/atajos';

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
export function Titlebar() {
  const [{ desktop, mac, win }, set] = useState({
    desktop: false,
    mac: false,
    win: false,
  });

  useEffect(() => {
    set(detectarPlataforma());
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
        <PlanBadge />
        <ReportButton />
        <Bell />
        {conControles && <WindowControls />}
      </div>
    </div>
  );
}
