'use client';

import { useEffect, useState } from 'react';

import { cn } from '@/lib/utils';
import { Icon } from '@/components/ui/icon';

interface WindowControlsApi {
  minimize: () => Promise<void>;
  toggleMaximize: () => Promise<boolean>;
  close: () => Promise<void>;
  isMaximized: () => Promise<boolean>;
  onMaximizedChanged: (cb: (maximized: boolean) => void) => () => void;
}

function getApi(): WindowControlsApi | null {
  if (typeof window === 'undefined') return null;
  const d = (window as unknown as {
    satDesktop?: { windowControls?: WindowControlsApi };
  }).satDesktop;
  return d?.windowControls ?? null;
}

/**
 * Controles de ventana de Windows (min / max-restaurar / cerrar) dibujados por
 * la app — en Windows la ventana corre con titleBarStyle 'hidden' (sin barra
 * nativa) y estos botones la reemplazan vía IPC del preload. Solo se montan
 * cuando el preload expone `satDesktop.windowControls` (Electron); en
 * macOS/navegador el Titlebar ni los renderea.
 */
export function WindowControls() {
  const [api, setApi] = useState<WindowControlsApi | null>(null);
  const [maximized, setMaximized] = useState(false);

  // Post-mount para no desincronizar la hidratación (SSR no ve el preload).
  useEffect(() => {
    const a = getApi();
    if (!a) return;
    setApi(a);
    let activo = true;
    a.isMaximized().then((m) => {
      if (activo) setMaximized(m);
    });
    const dispose = a.onMaximizedChanged(setMaximized);
    return () => {
      activo = false;
      dispose();
    };
  }, []);

  if (!api) return null;

  const btn =
    'flex h-full w-11.5 items-center justify-center text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground';

  return (
    <div
      className="flex h-full items-center"
      style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
    >
      <button className={btn} title="Minimizar" onClick={() => api.minimize()}>
        <Icon icon="ph:minus-light" className="size-3.5" />
      </button>
      <button
        className={btn}
        title={maximized ? 'Restaurar' : 'Maximizar'}
        onClick={() => api.toggleMaximize()}
      >
        {/* Cuadro = maximizar; dos cuadros encimados = restaurar (glifo Windows). */}
        <Icon
          icon={maximized ? 'ph:copy-light' : 'ph:square-light'}
          className="size-3"
        />
      </button>
      <button
        className={cn(btn, 'hover:bg-[var(--win-close)] hover:text-white')}
        title="Cerrar"
        onClick={() => api.close()}
      >
        <Icon icon="ph:x-light" className="size-3.5" />
      </button>
    </div>
  );
}
