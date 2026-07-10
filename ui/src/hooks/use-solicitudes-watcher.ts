'use client';

import { useEffect, useRef } from 'react';

import { useServer } from '@/providers/server-provider';
import { notifyDescargaCompleta, notifyDescargaError } from '@/lib/notify';
import type { SolicitudGlobal } from '@/lib/types';

// Cada cuánto se consulta la actividad de solicitudes de TODAS las empresas.
// El poller del agente verifica contra el SAT cada 60s; aquí solo leemos el
// catálogo local, así que 20s da sensación de inmediatez sin costo real.
const WATCH_INTERVAL_MS = 20_000;

const ESTADOS_EXITO = new Set(['3', 'descargada']);
const ESTADOS_FALLA = new Set(['4', '5', 'vencida']);

/**
 * Watcher global de solicitudes WS — cubre TODAS las empresas, no solo la
 * activa. El agente resuelve las solicitudes en background (poller); este
 * hook observa el catálogo y notifica las transiciones aunque el usuario esté
 * parado en otra empresa u otra pantalla:
 *
 *   - no-terminal → lista/descargada: toast/nativa de éxito (con la empresa).
 *   - no-terminal → error/rechazada/vencida: notificación de error (roja),
 *     para saber QUÉ empresa tuvo el problema.
 *
 * Montar UNA sola vez en el shell (junto a useEfirmaReminder). El primer
 * fetch solo toma la foto inicial (no notifica nada al abrir la app).
 */
export function useSolicitudesWatcher(): void {
  const { apiClient, isConnected } = useServer();

  // `${rfc}:${id}` → estado previo.
  const prevRef = useRef<Map<string, string>>(new Map());
  // Solicitudes ya notificadas con éxito en esta sesión: una que pasa por
  // "3" (lista) y luego "descargada" solo debe sonar una vez.
  const notificadasRef = useRef<Set<string>>(new Set());
  const primeraCargaRef = useRef(true);

  useEffect(() => {
    if (!isConnected) return;

    let cancelado = false;

    const tick = async () => {
      let solicitudes: SolicitudGlobal[];
      try {
        ({ solicitudes } = await apiClient.solicitudesActividad());
      } catch {
        return; // agente reiniciando / red local: reintenta en el siguiente tick
      }
      if (cancelado) return;

      const prev = prevRef.current;
      if (primeraCargaRef.current) {
        for (const s of solicitudes) prev.set(`${s.rfc}:${s.id_solicitud}`, s.estado);
        primeraCargaRef.current = false;
        return;
      }

      for (const s of solicitudes) {
        const key = `${s.rfc}:${s.id_solicitud}`;
        const estadoPrev = prev.get(key);
        prev.set(key, s.estado);
        if (estadoPrev === undefined) continue; // nueva en este ciclo: aún sin transición
        if (estadoPrev === s.estado) continue;

        const empresa = s.nombre || s.rfc;
        if (ESTADOS_EXITO.has(s.estado) && !ESTADOS_EXITO.has(estadoPrev)) {
          if (notificadasRef.current.has(key)) continue;
          notificadasRef.current.add(key);
          notifyDescargaCompleta({
            canal: 'ws',
            rfc: empresa,
            count: s.numero_cfdis,
            jobId: s.id_solicitud,
          });
        } else if (ESTADOS_FALLA.has(s.estado) && !ESTADOS_FALLA.has(estadoPrev)) {
          notifyDescargaError({
            canal: 'ws',
            rfc: empresa,
            motivo: s.mensaje,
            jobId: s.id_solicitud,
          });
        }
      }
    };

    void tick();
    const interval = setInterval(() => void tick(), WATCH_INTERVAL_MS);
    return () => {
      cancelado = true;
      clearInterval(interval);
    };
  }, [apiClient, isConnected]);
}
