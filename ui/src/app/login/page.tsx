'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Image from 'next/image';

import { useServer } from '@/providers/server-provider';
import { useAuth } from '@/providers/auth-provider';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Icon } from '@/components/ui/icon';

type Phase = 'idle' | 'iniciando' | 'esperando' | 'exito' | 'error';

const POLL_INTERVAL_MS = 2500;
const POLL_TIMEOUT_MS = 9 * 60 * 1000; // device code expira a 10 min en backend

export default function LoginPage() {
  const { apiClient } = useServer();
  const { refresh } = useAuth();

  const [phase, setPhase] = useState<Phase>('idle');
  const [deviceCode, setDeviceCode] = useState<string | null>(null);
  const [activateUrl, setActivateUrl] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startedAtRef = useRef<number>(0);

  const cleanup = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  useEffect(() => cleanup, [cleanup]);

  const iniciar = useCallback(async () => {
    cleanup();
    setPhase('iniciando');
    setErrorMsg(null);
    try {
      const r = await apiClient.authInit();
      setDeviceCode(r.device_code);
      setActivateUrl(r.activate_url);
      startedAtRef.current = Date.now();
      setPhase('esperando');

      pollTimerRef.current = setInterval(async () => {
        if (Date.now() - startedAtRef.current > POLL_TIMEOUT_MS) {
          cleanup();
          setErrorMsg(
            'El código de activación expiró. Genera uno nuevo y vuelve a intentar.',
          );
          setPhase('error');
          return;
        }
        try {
          const res = await apiClient.authPoll(r.device_code);
          if (res.status === 'ok') {
            cleanup();
            setPhase('exito');
            // Estilo Notion / 1Password: cuando la activación se completa en
            // el browser, la desktop se trae automáticamente al frente. Sin
            // esto, el usuario tiene que cambiarse de ventana manualmente.
            const w = window as unknown as {
              satDesktop?: { focusWindow?: () => Promise<boolean> };
            };
            w.satDesktop?.focusWindow?.().catch(() => {
              /* en browser/dev no hay satDesktop — no-op */
            });
            // Pequeña pausa para que el usuario vea el estado de éxito antes
            // de que `refresh()` re-renderee el shell con el dashboard.
            setTimeout(() => {
              refresh();
            }, 800);
          } else if (res.status === 'expired') {
            cleanup();
            setErrorMsg('El código expiró. Genera uno nuevo.');
            setPhase('error');
          } else if (res.status === 'not_found') {
            cleanup();
            setErrorMsg('El código fue invalidado. Genera uno nuevo.');
            setPhase('error');
          }
          // 'pending' → seguimos polling.
        } catch (e) {
          // Errores de red transitorios: no rompemos el polling, solo logueamos.
          console.warn('[login] poll falló:', e);
        }
      }, POLL_INTERVAL_MS);
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : String(e));
      setPhase('error');
    }
  }, [apiClient, cleanup, refresh]);

  // Auto-iniciar al cargar la página la primera vez.
  useEffect(() => {
    if (phase === 'idle') {
      iniciar();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Escucha deep links del protocolo `todoconta://activated?code=XXX`.
  // Cuando la web hace el redirect post-activate, el SO trae a esta app al
  // frente con el code; aquí hacemos un poll inmediato para no esperar el
  // próximo tick de polling regular (~2.5s) — UX más snappy.
  useEffect(() => {
    const w = window as unknown as {
      satDesktop?: {
        onProtocolActivated?: (
          cb: (payload: { action: string; code: string | null }) => void,
        ) => () => void;
      };
    };
    const subscribe = w.satDesktop?.onProtocolActivated;
    if (!subscribe) return;

    const dispose = subscribe(async ({ action, code }) => {
      if (action !== 'activated' || !code) return;
      try {
        const res = await apiClient.authPoll(code);
        if (res.status === 'ok') {
          cleanup();
          setPhase('exito');
          setTimeout(() => refresh(), 600);
        }
        // Si todavía está pending o el code no coincide con el del polling
        // regular, dejamos que el polling regular lo recoja.
      } catch (e) {
        console.warn('[login] poll desde deep link falló:', e);
      }
    });
    return dispose;
  }, [apiClient, cleanup, refresh]);

  const copyCode = useCallback(() => {
    if (deviceCode) {
      navigator.clipboard?.writeText(deviceCode).catch(() => {
        /* ignore */
      });
    }
  }, [deviceCode]);

  const openActivate = useCallback(() => {
    if (activateUrl) {
      window.open(activateUrl, '_blank', 'noopener,noreferrer');
    }
  }, [activateUrl]);

  return (
    <div className="min-h-screen bg-linear-to-b from-background to-muted/30 flex items-center justify-center p-6">
      <div className="w-full max-w-md space-y-4">
        <div className="text-center space-y-2">
          <Image
            src="/icon.png"
            alt="TodoConta"
            width={56}
            height={56}
            className="mx-auto rounded-xl"
            priority
          />
          <h1 className="text-2xl font-semibold">TodoConta Desktop</h1>
          <p className="text-sm text-muted-foreground">
            Inicia sesión para empezar
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Vincular a tu cuenta</CardTitle>
            <CardDescription>
              Necesitas una cuenta de TodoConta. Si aún no la tienes, créala
              gratis desde el navegador.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {(phase === 'iniciando' || phase === 'idle') && (
              <div className="flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground">
                <Icon icon="ph:circle-notch-light" className="size-4 animate-spin" />
                Generando código…
              </div>
            )}

            {phase === 'esperando' && deviceCode && (
              <>
                <ol className="space-y-3 text-sm">
                  <li className="flex gap-2">
                    <span className="font-mono text-xs text-muted-foreground pt-0.5">
                      1.
                    </span>
                    <div className="space-y-2 flex-1">
                      <p>Abre TodoConta en tu navegador:</p>
                      <Button
                        onClick={openActivate}
                        variant="outline"
                        size="sm"
                        className="w-full"
                      >
                        <Icon icon="ph:arrow-square-out-light" className="size-4" />
                        Abrir página de activación
                      </Button>
                    </div>
                  </li>
                  <li className="flex gap-2">
                    <span className="font-mono text-xs text-muted-foreground pt-0.5">
                      2.
                    </span>
                    <div className="space-y-2 flex-1">
                      <p>
                        Si te pide login, inicia sesión. Después confirma que el
                        código mostrado en la web coincide con éste:
                      </p>
                      <div className="rounded-md border bg-muted/40 p-3 text-center space-y-1">
                        <p className="text-xs text-muted-foreground">
                          Código de activación
                        </p>
                        <p className="font-mono text-2xl tracking-[0.4em] font-semibold">
                          {deviceCode}
                        </p>
                        <button
                          onClick={copyCode}
                          className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
                        >
                          <Icon icon="ph:copy-light" className="size-3" />
                          Copiar
                        </button>
                      </div>
                    </div>
                  </li>
                  <li className="flex gap-2">
                    <span className="font-mono text-xs text-muted-foreground pt-0.5">
                      3.
                    </span>
                    <p className="flex-1">
                      Cuando confirmes en la web, esta ventana entrará
                      automáticamente.
                    </p>
                  </li>
                </ol>
                <div className="flex items-center justify-center gap-2 pt-2 text-xs text-muted-foreground">
                  <Icon icon="ph:circle-notch-light" className="size-3 animate-spin" />
                  Esperando confirmación…
                </div>
              </>
            )}

            {phase === 'exito' && (
              <div className="space-y-2 py-4 text-center">
                <Icon
                  icon="ph:check-circle-fill"
                  className="mx-auto size-10 text-green-600"
                />
                <p className="text-sm font-medium">¡Listo!</p>
                <p className="text-xs text-muted-foreground">
                  Entrando a TodoConta Desktop…
                </p>
              </div>
            )}

            {phase === 'error' && (
              <>
                <Alert variant="destructive">
                  <AlertTitle>No pudimos completar el login</AlertTitle>
                  <AlertDescription>
                    {errorMsg ?? 'Error desconocido'}
                  </AlertDescription>
                </Alert>
                <Button onClick={iniciar} variant="outline" className="w-full">
                  <Icon icon="ph:arrow-clockwise-light" className="size-4" />
                  Intentar de nuevo
                </Button>
              </>
            )}
          </CardContent>
        </Card>

        <p className="text-center text-xs text-muted-foreground">
          Tu e.firma y datos de empresas viven solo en este equipo. La cuenta
          es para licencia y actualizaciones.
        </p>
      </div>
    </div>
  );
}
