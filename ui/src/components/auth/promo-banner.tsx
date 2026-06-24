'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

import { useAuth } from '@/providers/auth-provider';
import { Button } from '@/components/ui/button';
import { Icon } from '@/components/ui/icon';
import { diasRestantes, formatPesosEnteros } from '@/lib/formatting';

/**
 * Banner de la promo de conversión: 50% en el plan anual, bloqueado de por vida.
 *
 * Solo se renderea si:
 *   - El usuario está autenticado.
 *   - Su plan es `trial` o `free` (aún no paga).
 *   - La promo está activa para él (`promo_active`): el kill switch global está
 *     encendido Y sigue dentro de sus primeros días (`promo_ends_at`).
 *
 * El CTA lleva a la página interna `/suscripcion` (no abre el navegador): ahí el
 * usuario elige tarjeta o transferencia.
 *
 * El botón de cerrar oculta el banner solo por esta sesión (estado local, sin
 * persistencia): reaparece la próxima vez que se abre la app si la promo sigue
 * activa.
 */
export function PromoBanner() {
  const { license } = useAuth();
  const router = useRouter();
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;
  if (!license || !license.authenticated) return null;
  if (!license.promo_active) return null;
  if (license.plan !== 'trial' && license.plan !== 'free') return null;

  const regular =
    typeof license.regular_price_mxn === 'number'
      ? formatPesosEnteros(license.regular_price_mxn)
      : null;
  const promo =
    typeof license.promo_price_mxn === 'number'
      ? formatPesosEnteros(license.promo_price_mxn)
      : null;

  const dias = diasRestantes(license.promo_ends_at);

  return (
    <div className="border-b border-primary/20 bg-primary/5">
      <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-2">
        <span className="flex size-6 shrink-0 items-center justify-center rounded-[6px] bg-primary text-primary-foreground">
          <Icon icon="ph:percent-light" className="size-3.5" />
        </span>
        <p className="min-w-0 flex-1 truncate text-[13px] leading-snug">
          <strong className="font-bold text-foreground">
            50% de por vida en tu plan anual.
          </strong>{' '}
          {regular && promo ? (
            <>
              <strong className="font-semibold text-foreground">{promo}/año</strong>{' '}
              en lugar de{' '}
              <span className="text-muted-foreground">{regular}</span>, congelado
              mientras no canceles.
            </>
          ) : (
            'Precio congelado mientras no canceles.'
          )}
          {dias !== null && (
            <span className="ml-1 font-semibold text-primary">
              {dias > 0
                ? `Te ${dias === 1 ? 'queda 1 día' : `quedan ${dias} días`}.`
                : 'Último día.'}
            </span>
          )}
        </p>

        <Button
          onClick={() => router.push('/suscripcion')}
          size="sm"
          className="shrink-0"
        >
          <Icon icon="ph:lightning-light" className="size-4" />
          Quiero el 50%
        </Button>
        <button
          type="button"
          onClick={() => setDismissed(true)}
          aria-label="Ocultar promoción"
          title="Ocultar"
          className="flex size-7 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-primary/10 hover:text-foreground"
        >
          <Icon icon="ph:x-light" className="size-4" />
        </button>
      </div>
    </div>
  );
}
