'use client';

import { formatDistanceToNow } from 'date-fns';
import { es } from 'date-fns/locale';

import { cn } from '@/lib/utils';
import { semaforoVencimiento } from '@/lib/vencimiento';
import { useEmpresas } from '@/hooks/use-empresas';
import { useStatusBarStats } from '@/hooks/use-status-bar-stats';
import { useServer } from '@/providers/server-provider';
import { Icon } from '@/components/ui/icon';
import type { Empresa } from '@/lib/types';

interface EfirmaItem {
  tono: 'green' | 'amber' | 'red' | 'muted';
  icono: string;
  texto: string;
}

/**
 * Estado de e.firma de la empresa activa para la barra: semáforo por vigencia
 * (verde >30 días · amarillo ≤30 · rojo ≤5 o vencida) o neutro para solo-CIEC.
 */
function efirmaItem(empresa: Empresa | null): EfirmaItem | null {
  if (!empresa) return null;
  if (!empresa.metodos.includes('fiel')) {
    return { tono: 'muted', icono: 'ph:key-light', texto: 'Acceso con CIEC' };
  }
  const sem = semaforoVencimiento(empresa.vencimiento);
  if (!sem) return null;
  if (sem.vencida) {
    return { tono: 'red', icono: 'ph:warning-circle-light', texto: 'e.firma vencida' };
  }
  if (sem.estado === 'verde') {
    const dias = `${sem.dias} ${sem.dias === 1 ? 'día' : 'días'}`;
    return { tono: 'green', icono: 'ph:key-light', texto: `e.firma vigente · ${dias}` };
  }
  return {
    tono: sem.estado === 'rojo' ? 'red' : 'amber',
    icono: 'ph:warning-light',
    // sem.label: "Vence en N días" / "Vence hoy" / "Vence mañana".
    texto: `e.firma ${sem.label.charAt(0).toLowerCase()}${sem.label.slice(1)}`,
  };
}

const TONOS: Record<EfirmaItem['tono'], string> = {
  green: 'font-semibold text-success [&_svg]:text-success',
  amber: 'font-semibold text-warning [&_svg]:text-warning',
  red: 'font-semibold text-destructive [&_svg]:text-destructive',
  muted: '',
};

/**
 * Barra de estado inferior fija: conexión con el agente a la izquierda;
 * estadísticas de la empresa activa (CFDIs del mes, última descarga, e.firma)
 * a la derecha. Visible en todas las pantallas.
 */
export function StatusBar() {
  const { isConnected } = useServer();
  const { empresas } = useEmpresas();

  const activas = empresas.filter((e) => !e.archived_at);
  const activa = activas.find((e) => e.default) ?? activas[0] ?? null;
  const stats = useStatusBarStats(activa?.rfc ?? null);
  const ef = efirmaItem(activa);

  return (
    <div className="flex h-7.5 shrink-0 select-none items-center justify-between gap-4 border-t bg-card px-4 text-xs text-muted-foreground">
      <div className="flex items-center gap-1.5">
        <span
          className={cn(
            'size-1.75 rounded-full',
            isConnected
              ? 'bg-success shadow-[0_0_6px_var(--success)]'
              : 'bg-destructive',
          )}
        />
        <span
          className={cn(
            'font-semibold',
            isConnected ? 'text-success' : 'text-destructive',
          )}
        >
          {isConnected ? 'Conectado' : 'Desconectado'}
        </span>
      </div>

      <div className="flex min-w-0 items-center gap-3">
        {stats && (
          <>
            <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
              <Icon icon="ph:files-light" className="size-3.5" />
              {stats.cfdisMes.toLocaleString('es-MX')} CFDIs este mes
            </span>
            {stats.ultimaDescarga && (
              <>
                <span className="h-3 w-px bg-border" />
                <span className="hidden items-center gap-1.5 whitespace-nowrap sm:inline-flex">
                  <Icon icon="ph:clock-counter-clockwise-light" className="size-3.5" />
                  Última descarga:{' '}
                  {formatDistanceToNow(stats.ultimaDescarga, {
                    locale: es,
                    addSuffix: true,
                  })}
                </span>
              </>
            )}
          </>
        )}
        {ef && (
          <>
            {stats && <span className="h-3 w-px bg-border" />}
            <span
              className={cn(
                'inline-flex items-center gap-1.5 whitespace-nowrap',
                TONOS[ef.tono],
              )}
            >
              <Icon icon={ef.icono} className="size-3.5" />
              {ef.texto}
            </span>
          </>
        )}
      </div>
    </div>
  );
}
