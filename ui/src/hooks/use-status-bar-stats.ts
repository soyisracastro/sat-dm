'use client';

import { useEffect, useState } from 'react';

import { useServer } from '@/providers/server-provider';

export interface StatusBarStats {
  /** CFDIs descargados en el mes en curso (suma de totales del historial). */
  cfdisMes: number;
  /** Timestamp de la descarga más reciente (cualquier tipo), o null. */
  ultimaDescarga: Date | null;
}

/**
 * Estadísticas de la barra de estado, derivadas del historial de la empresa
 * activa. Refresca al montar, al cambiar de empresa (`empresas:refresh`), al
 * volver el foco a la ventana y cada 60 s. Los fallos son silenciosos: la
 * barra simplemente no muestra el dato.
 */
export function useStatusBarStats(rfc: string | null): StatusBarStats | null {
  const { apiClient } = useServer();
  const [stats, setStats] = useState<StatusBarStats | null>(null);

  useEffect(() => {
    if (!rfc) {
      setStats(null);
      return;
    }
    let activo = true;

    const cargar = () => {
      apiClient
        .listHistorialEmpresa(rfc)
        .then((r) => {
          if (!activo) return;
          const ahora = new Date();
          let cfdisMes = 0;
          let ultimaDescarga: Date | null = null;
          for (const d of r.descargas) {
            const t = new Date(d.timestamp);
            if (Number.isNaN(t.getTime())) continue;
            if (!ultimaDescarga || t > ultimaDescarga) ultimaDescarga = t;
            if (
              d.tipo === 'cfdi' &&
              typeof d.total === 'number' &&
              t.getFullYear() === ahora.getFullYear() &&
              t.getMonth() === ahora.getMonth()
            ) {
              cfdisMes += d.total;
            }
          }
          setStats({ cfdisMes, ultimaDescarga });
        })
        .catch(() => {
          if (activo) setStats(null);
        });
    };

    cargar();
    window.addEventListener('empresas:refresh', cargar);
    window.addEventListener('focus', cargar);
    const intervalo = setInterval(cargar, 60_000);
    return () => {
      activo = false;
      window.removeEventListener('empresas:refresh', cargar);
      window.removeEventListener('focus', cargar);
      clearInterval(intervalo);
    };
  }, [apiClient, rfc]);

  return stats;
}
