'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Icon } from '@/components/ui/icon';
import type { PagosStats } from '@/lib/types';

interface Props {
  stats: PagosStats | null;
}

function formatoMXN(n: number): string {
  return new Intl.NumberFormat('es-MX', {
    style: 'currency',
    currency: 'MXN',
    minimumFractionDigits: 2,
  }).format(n);
}

export function PagosStatsCards({ stats }: Props) {
  const total = stats?.total_ingresos_ppd ?? 0;
  const totalGlobal = stats?.total_global_ppd ?? 0;
  const pct = stats?.porcentaje_conciliados ?? 0;
  const sinComp = stats?.sin_complemento ?? 0;
  const parciales = stats?.pagos_parciales ?? 0;
  const completos = stats?.pagos_completos ?? 0;
  const sobrantes = stats?.sobrantes ?? 0;
  const montoPendiente = stats?.monto_total_sin_pagar ?? 0;
  const huerfanos = stats?.pagos_huerfanos ?? 0;
  const incidPue = stats?.incidencias_pue ?? 0;
  const extemp = stats?.complementos_extemporaneos ?? 0;
  const hayFiltros = totalGlobal > 0 && total !== totalGlobal;
  const hayProblemas = huerfanos > 0 || incidPue > 0 || extemp > 0;

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Icon icon="ph:check-circle-light" className="size-4" />
            Conciliadas
          </CardTitle>
          <CardDescription>% de facturas PPD con pago completo</CardDescription>
        </CardHeader>
        <CardContent className="space-y-1">
          <div className="text-2xl font-semibold">
            {pct.toLocaleString('es-MX', { maximumFractionDigits: 1 })}%
          </div>
          <p className="text-xs text-muted-foreground">
            {total.toLocaleString('es-MX')} PPD
            {hayFiltros && ` de ${totalGlobal.toLocaleString('es-MX')}`}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Icon icon="ph:hourglass-medium-light" className="size-4" />
            Saldo pendiente
          </CardTitle>
          <CardDescription>Monto sin pagar (PPD)</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-semibold">{formatoMXN(montoPendiente)}</div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Icon icon="ph:list-numbers-light" className="size-4" />
            Desglose
          </CardTitle>
          <CardDescription>Status de cada PPD</CardDescription>
        </CardHeader>
        <CardContent className="space-y-1 text-xs">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Sin complemento:</span>
            <span className="font-mono">{sinComp}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Parciales:</span>
            <span className="font-mono">{parciales}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Completos:</span>
            <span className="font-mono">{completos}</span>
          </div>
          {sobrantes > 0 && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Sobrantes:</span>
              <span className="font-mono">{sobrantes}</span>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className={hayProblemas ? 'border-amber-300' : undefined}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Icon icon="ph:warning-light" className="size-4" />
            Incidencias
          </CardTitle>
          <CardDescription>Problemas detectados</CardDescription>
        </CardHeader>
        <CardContent className="space-y-1 text-xs">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Huérfanos:</span>
            <span className="font-mono">{huerfanos}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">PUE+complemento:</span>
            <span className="font-mono">{incidPue}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Extemporáneos:</span>
            <span className="font-mono">{extemp}</span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
