'use client';

import { useEffect, useState } from 'react';

import { Icon } from '@/components/ui/icon';

/**
 * Pantalla de carga inicial mostrada mientras el agente local arranca y el
 * AuthProvider hace su primer `/auth/license`. Evoluciona el mensaje según
 * cuánto lleva esperando:
 *
 *   0–15s   "Cargando…" estándar.
 *   15–60s  Aviso de que el primer arranque puede tardar mientras Windows
 *           revisa los archivos (AV scanning).
 *   >60s    Botón "Reintentar" — en lugar de un blank eterno.
 *
 * Pensado para que el usuario de Windows con Defender activo entienda QUÉ
 * está pasando y no asuma que la app está rota cuando solo está esperando
 * un scan de antivirus.
 */
export function StartupSplash() {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, []);

  const fase: 'inicial' | 'esperando' | 'lento' =
    seconds < 15 ? 'inicial' : seconds < 60 ? 'esperando' : 'lento';

  return (
    <div className="flex h-full flex-1 items-center justify-center px-6">
      <div className="flex max-w-md flex-col items-center gap-4 text-center">
        <Icon
          icon="ph:circle-notch-light"
          className="size-8 animate-spin text-muted-foreground"
        />

        {fase === 'inicial' && (
          <p className="text-sm text-muted-foreground">Cargando…</p>
        )}

        {fase === 'esperando' && (
          <div className="space-y-2">
            <p className="text-sm font-medium">Iniciando el agente local…</p>
            <p className="text-xs text-muted-foreground leading-relaxed">
              En el primer arranque puede tardar hasta un minuto mientras
              Windows Defender revisa los archivos de TodoConta. Las próximas
              veces será inmediato.
            </p>
          </div>
        )}

        {fase === 'lento' && (
          <div className="space-y-3">
            <p className="text-sm font-medium">El agente está tardando más de lo normal.</p>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Esto suele pasar cuando un antivirus está escaneando los archivos.
              Si el problema persiste, cierra la app desde el Administrador de
              tareas y vuelve a abrirla.
            </p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="inline-flex items-center gap-2 rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium shadow-sm hover:bg-accent hover:text-accent-foreground"
            >
              <Icon icon="ph:arrow-clockwise-light" className="size-4" />
              Reintentar
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
