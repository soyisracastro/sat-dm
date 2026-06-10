'use client';

import { useState } from 'react';
import { toast } from 'sonner';

import { useServer } from '@/providers/server-provider';
import { useAuth } from '@/providers/auth-provider';
import { Button } from '@/components/ui/button';
import { Icon } from '@/components/ui/icon';
import { mensajeDeError } from '@/lib/errores';

/**
 * Banner persistente con CTA a hacerse Fundador.
 *
 * Solo se renderea si:
 *   - El usuario está autenticado.
 *   - El usuario NO es fundador todavía.
 *   - La ventana de fundadores está abierta (`founder_window_open=true`).
 *
 * Copy con FOMO sin números (regla del producto: nunca exponer el conteo
 * actual de fundadores ni cuántos lugares quedan).
 */
export function FounderBanner() {
  const { license } = useAuth();
  const { apiClient } = useServer();
  const [busy, setBusy] = useState(false);

  if (!license || !license.authenticated) return null;
  if (license.is_founder) return null;
  if (!license.founder_window_open) return null;

  const price =
    typeof license.founder_price_mxn === 'number'
      ? new Intl.NumberFormat('es-MX', {
          style: 'currency',
          currency: 'MXN',
          minimumFractionDigits: 0,
        }).format(license.founder_price_mxn)
      : null;

  async function comprar() {
    setBusy(true);
    try {
      const { url } = await apiClient.authUpgrade();
      // Abrimos en el navegador del SO; la desktop sigue corriendo y al
      // próximo refresh del license el `is_founder` se actualizará.
      window.open(url, '_blank', 'noopener,noreferrer');
      toast.info(
        'Te abrimos el navegador para pagar. Vuelve aquí cuando termines — esta ventana se actualizará sola.',
      );
    } catch (e) {
      toast.error(mensajeDeError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="border-b border-primary/20 bg-primary/5">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-2.5">
        <div className="flex items-center gap-2 text-sm">
          <Icon icon="ph:star-light" className="size-4 text-primary" />
          <span>
            <strong className="font-medium">Sé uno de los Contadores Fundadores.</strong>{' '}
            Acceso de por vida a todas las features no-IA{price ? ` por ${price}` : ''}.
            <span className="ml-1 text-muted-foreground">
              Quedan pocos lugares — oferta por tiempo limitado.
            </span>
          </span>
        </div>
        <Button onClick={comprar} disabled={busy} size="sm">
          <Icon
            icon={busy ? 'ph:circle-notch-light' : 'ph:rocket-light'}
            className={busy ? 'size-4 animate-spin' : 'size-4'}
          />
          Quiero ser fundador
        </Button>
      </div>
    </div>
  );
}
