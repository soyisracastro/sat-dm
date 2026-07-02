'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';

import { cn } from '@/lib/utils';
import { mensajeDeError } from '@/lib/errores';
import { useEmpresas } from '@/hooks/use-empresas';
import type { Empresa } from '@/lib/types';
import { EmpresaBadge } from '@/components/empresas/empresa-badge';
import { Icon } from '@/components/ui/icon';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

/**
 * Selector de empresa activa del sidebar: badge PF/PM + nombre truncado + RFC.
 * Abre un menú con todas las empresas (la activa con check) y un acceso a
 * "Administrar empresas". Cambiar de empresa usa `seleccionar()` (default +
 * carga de e.firma); el evento `empresas:refresh` sincroniza el resto de la UI.
 */
export function EmpresaSwitcher({ collapsed }: { collapsed: boolean }) {
  const router = useRouter();
  const { empresas, seleccionar } = useEmpresas();
  const [cambiando, setCambiando] = useState(false);

  const activas = empresas.filter((e) => !e.archived_at);
  const activa = activas.find((e) => e.default) ?? activas[0] ?? null;

  async function onSelect(e: Empresa) {
    if (cambiando || e.rfc === activa?.rfc) return;
    setCambiando(true);
    try {
      await seleccionar(e.rfc, e.metodos);
    } catch (err) {
      toast.error(mensajeDeError(err));
    } finally {
      setCambiando(false);
    }
  }

  if (!activa) {
    // Catálogo vacío (o aún cargando): acceso directo al alta.
    return (
      <button
        onClick={() => router.push('/empresas')}
        title={collapsed ? 'Agregar empresa' : undefined}
        className={cn(
          'flex items-center gap-2 rounded-lg border border-dashed text-sm font-medium text-muted-foreground transition-colors hover:border-primary hover:text-primary',
          collapsed ? 'justify-center p-2' : 'w-full px-3 py-2.5',
        )}
      >
        <Icon icon="ph:plus-light" className="size-4 shrink-0" />
        {!collapsed && 'Agregar empresa'}
      </button>
    );
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          title={collapsed ? `${activa.nombre} · ${activa.rfc}` : undefined}
          className={cn(
            'flex items-center gap-2.5 rounded-[10px] border bg-card text-left transition-colors hover:bg-secondary',
            collapsed ? 'justify-center p-1.5' : 'w-full px-2.5 py-2',
          )}
        >
          <EmpresaBadge rfc={activa.rfc} />
          {!collapsed && (
            <>
              <span className="flex min-w-0 flex-1 flex-col gap-px">
                <span className="truncate text-[12.5px] font-semibold leading-tight text-foreground">
                  {activa.nombre}
                </span>
                <span className="truncate font-mono text-[11px] text-muted-foreground">
                  {activa.rfc}
                </span>
              </span>
              <Icon
                icon={cambiando ? 'ph:circle-notch-light' : 'ph:caret-down-light'}
                className={cn(
                  'size-4 shrink-0 text-muted-foreground',
                  cambiando && 'animate-spin',
                )}
              />
            </>
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        side={collapsed ? 'right' : 'bottom'}
        align="start"
        className={cn(
          'rounded-xl',
          collapsed ? 'w-64' : 'w-[var(--radix-dropdown-menu-trigger-width)]',
        )}
      >
        <DropdownMenuLabel className="uppercase tracking-wide">
          Cambiar de empresa
        </DropdownMenuLabel>
        <div className="max-h-72 overflow-y-auto">
          {activas.map((e) => {
            const esActiva = e.rfc === activa.rfc;
            return (
              <DropdownMenuItem
                key={e.rfc}
                onSelect={() => onSelect(e)}
                className={cn('gap-2.5 rounded-lg', esActiva && 'bg-accent')}
              >
                <EmpresaBadge rfc={e.rfc} size="sm" />
                <span className="flex min-w-0 flex-1 flex-col gap-px">
                  <span className="truncate text-[12.5px] font-semibold leading-tight">
                    {e.nombre}
                  </span>
                  <span className="truncate font-mono text-[11px] text-muted-foreground">
                    {e.rfc}
                  </span>
                </span>
                {esActiva && (
                  <Icon
                    icon="ph:check-circle-light"
                    className="size-4 shrink-0 text-success"
                  />
                )}
              </DropdownMenuItem>
            );
          })}
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onSelect={() => router.push('/empresas')}
          className="gap-2 rounded-lg font-semibold text-primary focus:text-primary"
        >
          <Icon icon="ph:buildings-light" className="size-4" />
          Administrar empresas
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
