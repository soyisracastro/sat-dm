'use client';

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
 */
export function PromoBanner() {
  const { license } = useAuth();
  const router = useRouter();

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
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-2.5">
        <div className="flex items-center gap-2 text-sm">
          <Icon icon="ph:percent-light" className="size-4 shrink-0 text-primary" />
          <span>
            <strong className="font-medium">50% en tu plan anual, de por vida.</strong>{' '}
            {regular && promo ? (
              <>
                <span className="text-muted-foreground line-through">{regular}</span>{' '}
                <span className="font-medium">{promo}/año</span> mientras no canceles.
              </>
            ) : (
              'Asegura el mejor precio de por vida mientras no canceles.'
            )}
            {dias !== null && (
              <span className="ml-1 text-muted-foreground">
                {dias > 0
                  ? `Te ${dias === 1 ? 'queda 1 día' : `quedan ${dias} días`}.`
                  : 'Último día.'}
              </span>
            )}
          </span>
        </div>
        <Button onClick={() => router.push('/suscripcion')} size="sm">
          <Icon icon="ph:lightning-light" className="size-4" />
          Aprovechar oferta
        </Button>
      </div>
    </div>
  );
}
