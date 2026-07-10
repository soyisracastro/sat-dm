import { PanelInicio, PanelVacio } from '@/components/inicio/panel-inicio';
import { formatNumber } from '@/lib/formatting';
import type { MovimientoEmpresa } from '@/lib/inicio-stats';

interface EmpresasMovimientoProps {
  items: MovimientoEmpresa[];
  cargando: boolean;
}

/** Top de empresas por CFDIs descargados en el mes en curso. */
export function EmpresasMovimiento({
  items,
  cargando,
}: EmpresasMovimientoProps) {
  const maximo = items[0]?.total ?? 0;

  return (
    <PanelInicio
      titulo="Empresas con más movimiento"
      icono="ph:trend-up-light"
      sub="CFDIs este mes"
    >
      {cargando && items.length === 0 ? (
        <div className="h-[120px] animate-pulse rounded-lg bg-secondary/60" />
      ) : items.length === 0 ? (
        <PanelVacio icono="ph:download-simple-light">
          Aún no hay descargas de CFDIs este mes.
        </PanelVacio>
      ) : (
        <div className="flex flex-col gap-3">
          {items.map((m) => (
            <div
              key={m.rfc}
              className="grid grid-cols-[minmax(0,150px)_1fr_auto] items-center gap-3"
            >
              <span
                className="truncate text-[13px] font-semibold"
                title={m.nombre}
              >
                {m.nombre}
              </span>
              <div className="h-2 overflow-hidden rounded-full bg-secondary">
                <div
                  className="h-full rounded-full bg-primary"
                  style={{ width: `${(m.total / maximo) * 100}%` }}
                />
              </div>
              <span className="font-mono text-xs font-bold tabular-nums text-muted-foreground">
                {formatNumber(m.total)}
              </span>
            </div>
          ))}
        </div>
      )}
    </PanelInicio>
  );
}
