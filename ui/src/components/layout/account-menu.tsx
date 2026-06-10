'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';

import { cn } from '@/lib/utils';
import { iniciales } from '@/lib/empresa-visual';
import { mensajeDeError } from '@/lib/errores';
import { useAuth } from '@/providers/auth-provider';
import { useServer } from '@/providers/server-provider';
import { Icon } from '@/components/ui/icon';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

/**
 * Pill de cuenta del footer del sidebar: avatar con iniciales (corona si es
 * Fundador) + email. Abre hacia arriba el menú "Mi cuenta" con Ajustes,
 * Suscripción y cuenta, y Cerrar sesión.
 */
export function AccountMenu({ collapsed }: { collapsed: boolean }) {
  const router = useRouter();
  const { license, logout } = useAuth();
  const { apiClient } = useServer();
  const [busy, setBusy] = useState(false);

  const email = license?.email ?? null;
  const esFundador = !!license?.is_founder;
  const plan = esFundador ? 'Fundador' : 'Gratis';

  async function abrirSuscripcion() {
    if (busy) return;
    // Fundador: ya tiene el plan — lo mandamos a su cuenta en la web.
    // Sin plan: abrimos el checkout de upgrade (mismo flujo que el banner).
    if (esFundador) {
      window.open('https://app.todoconta.com', '_blank', 'noopener,noreferrer');
      return;
    }
    setBusy(true);
    try {
      const { url } = await apiClient.authUpgrade();
      window.open(url, '_blank', 'noopener,noreferrer');
    } catch (e) {
      toast.error(mensajeDeError(e));
    } finally {
      setBusy(false);
    }
  }

  const avatar = (
    <span className="relative flex size-8.5 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
      {email ? iniciales(email) : <Icon icon="ph:user-light" className="size-4" />}
      {esFundador && (
        <span className="absolute -left-1 -top-1.5 -rotate-[18deg] text-amber-500">
          <Icon icon="ph:crown-simple-fill" className="size-3" />
        </span>
      )}
    </span>
  );

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          title={collapsed && email ? email : undefined}
          className={cn(
            'flex items-center gap-2.5 rounded-xl border border-transparent text-left transition-colors',
            'hover:border-border hover:bg-card data-[state=open]:border-border data-[state=open]:bg-card',
            collapsed ? 'justify-center p-1' : 'w-full px-2 py-1.5',
          )}
        >
          {avatar}
          {!collapsed && (
            <>
              <span className="flex min-w-0 flex-1 flex-col gap-px">
                <span className="truncate text-[13px] font-semibold leading-tight text-foreground">
                  Mi cuenta
                </span>
                {email && (
                  <span className="truncate text-[11.5px] text-muted-foreground">
                    {email}
                  </span>
                )}
              </span>
              <Icon
                icon="ph:caret-up-light"
                className="size-4 shrink-0 text-muted-foreground"
              />
            </>
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        side={collapsed ? 'right' : 'top'}
        align={collapsed ? 'end' : 'start'}
        className={cn(
          'rounded-xl',
          collapsed ? 'w-60' : 'w-[var(--radix-dropdown-menu-trigger-width)]',
        )}
      >
        <div className="px-3 pb-2 pt-2.5">
          <div className="mb-0.5 flex items-center justify-between gap-2">
            <span className="text-[15px] font-bold text-foreground">Mi cuenta</span>
            <span className="inline-flex items-center gap-1 rounded-full bg-accent px-2.5 py-0.5 text-[11px] font-bold text-accent-foreground">
              {esFundador && (
                <Icon icon="ph:crown-simple-fill" className="size-3 text-amber-500" />
              )}
              {plan}
            </span>
          </div>
          {email && (
            <span className="block truncate text-[11.5px] text-muted-foreground">
              {email}
            </span>
          )}
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onSelect={() => router.push('/ajustes')}
          className="gap-2.5 rounded-lg"
        >
          <Icon icon="ph:gear-light" className="size-4 text-muted-foreground" />
          Ajustes
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={abrirSuscripcion} className="gap-2.5 rounded-lg">
          <Icon
            icon={busy ? 'ph:circle-notch-light' : 'ph:credit-card-light'}
            className={cn('size-4 text-muted-foreground', busy && 'animate-spin')}
          />
          Suscripción y cuenta
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onSelect={() => logout()}
          className="gap-2.5 rounded-lg text-destructive focus:bg-destructive/10 focus:text-destructive"
        >
          <Icon icon="ph:sign-out-light" className="size-4" />
          Cerrar sesión
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
