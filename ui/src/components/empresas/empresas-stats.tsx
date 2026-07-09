import { cn } from '@/lib/utils';
import { tipoPersona } from '@/lib/empresa-visual';
import { requiereAtencion } from '@/lib/empresas-filtro';
import type { Empresa } from '@/lib/types';

/**
 * Barra de totales de la vista de activas: N activas · N morales · N físicas ·
 * N requieren atención (en ámbar cuando hay alguna).
 */
export function EmpresasStats({ empresas }: { empresas: Empresa[] }) {
  const nPM = empresas.filter((e) => tipoPersona(e.rfc) === 'PM').length;
  const nPF = empresas.length - nPM;
  const nAtencion = empresas.filter(requiereAtencion).length;

  return (
    <div className="flex items-stretch overflow-x-auto rounded-xl border border-border bg-card p-1">
      <Stat valor={empresas.length} label={empresas.length === 1 ? 'activa' : 'activas'} />
      <Stat valor={nPM} label="morales" dotClass="bg-violet-600" divider />
      <Stat valor={nPF} label="físicas" dotClass="bg-cyan-600" divider />
      <Stat
        valor={nAtencion}
        label="requieren atención"
        valorClass={nAtencion > 0 ? 'text-warning' : undefined}
        divider
      />
    </div>
  );
}

function Stat({
  valor,
  label,
  dotClass,
  valorClass,
  divider,
}: {
  valor: number;
  label: string;
  dotClass?: string;
  valorClass?: string;
  divider?: boolean;
}) {
  return (
    <div
      className={cn(
        'flex items-baseline gap-1.5 whitespace-nowrap px-4 py-2',
        divider && 'border-l border-border/60',
      )}
    >
      {dotClass && <span className={cn('size-2 self-center rounded-full', dotClass)} />}
      <span className={cn('text-lg font-bold tabular-nums', valorClass)}>{valor}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  );
}
