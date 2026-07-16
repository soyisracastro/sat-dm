'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

import { Icon } from '@/components/ui/icon';

/**
 * /planes — alias de /suscripcion.
 *
 * Es el destino canónico de los links externos de pricing (landing, correos de
 * la serie de conversión, campañas). Antes se proxeaba al legacy de apps/web
 * (diseño viejo, sesión por cookies); ahora resuelve nativo en el espejo: el
 * usuario llega logueado con su agente y ve SU precio (promo/founder aplicados
 * por el server). Ruta estática (cumple `output: 'export'`).
 */
export default function PlanesPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/suscripcion');
  }, [router]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 text-muted-foreground">
      <Icon icon="ph:circle-notch-light" className="size-6 animate-spin" />
      <p className="text-sm">
        Llevándote a tu suscripción…{' '}
        <a href="/suscripcion" className="font-semibold text-primary hover:underline">
          o entra aquí
        </a>
      </p>
    </div>
  );
}
