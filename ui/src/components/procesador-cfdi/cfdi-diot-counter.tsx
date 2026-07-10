'use client';

import { Icon } from '@/components/ui/icon';
import type { CfdiStats } from '@/lib/types';

/**
 * Línea discreta sobre la tabla: cuántas operaciones del buffer pasan a la
 * DIOT y el estado de la clasificación de deducibilidad. Los contadores son
 * GLOBALES de la empresa (no cambian con los filtros de la tabla). Con
 * `mostrarDiot=false` (empresa relevada, p. ej. RESICO) solo se reporta la
 * deducibilidad — o nada, si no hay clasificaciones que contar.
 */
export function CfdiDiotCounter({
  stats,
  mostrarDiot = true,
}: {
  stats: CfdiStats;
  mostrarDiot?: boolean;
}) {
  const {
    diot_elegibles: elegibles,
    diot_pasan: pasan,
    diot_no_aplica: noAplica,
    deducible_no: noDeducibles,
    deducible_sin_clasificar: sinClasificar,
  } = stats;

  if (!mostrarDiot && noDeducibles === 0 && sinClasificar === 0) return null;

  if (!mostrarDiot) {
    return (
      <div className="flex items-center gap-2 px-0.5 text-xs text-muted-foreground">
        <Icon icon="ph:file-text-light" className="size-3.5 shrink-0 text-primary" />
        <span>
          {noDeducibles > 0 && (
            <>
              <b className="font-semibold text-foreground/80">{noDeducibles}</b> no
              deducible{noDeducibles !== 1 ? 's' : ''}
              {sinClasificar > 0 && ' · '}
            </>
          )}
          {sinClasificar > 0 && <>{sinClasificar} sin clasificar</>}
        </span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 px-0.5 text-xs text-muted-foreground">
      <Icon icon="ph:file-text-light" className="size-3.5 shrink-0 text-primary" />
      <span>
        <b className="font-semibold text-foreground/80">{pasan}</b> de{' '}
        <b className="font-semibold text-foreground/80">{elegibles}</b> operaciones pasan a
        la DIOT
        {noAplica > 0 && (
          <>
            {' · '}
            <span title="Complementos de pago, nómina, traslados y comprobantes emitidos no se declaran en la DIOT.">
              {noAplica} no aplican
            </span>
          </>
        )}
        {noDeducibles > 0 && (
          <>
            {' · '}
            <b className="font-semibold text-foreground/80">{noDeducibles}</b> no deducible
            {noDeducibles !== 1 ? 's' : ''}
          </>
        )}
        {sinClasificar > 0 && <> · {sinClasificar} sin clasificar</>}
      </span>
    </div>
  );
}
