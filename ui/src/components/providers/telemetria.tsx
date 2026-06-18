'use client';

import { useEffect } from 'react';

import { initTelemetria } from '@/lib/telemetria';

/**
 * Monta la telemetría de errores (Sentry) una sola vez al cargar el renderer.
 * No renderiza nada. Solo se activa dentro de Electron y con DSN configurado en
 * el proceso main; en el navegador/dev es no-op.
 */
export function Telemetria() {
  useEffect(() => {
    void initTelemetria();
  }, []);
  return null;
}
