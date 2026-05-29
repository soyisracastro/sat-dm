import { Icon } from '@/components/ui/icon';
import { cn } from '@/lib/utils';
import { semaforoVencimiento } from '@/lib/vencimiento';
import type { Empresa } from '@/lib/types';

type Tone = 'verde' | 'amarillo' | 'rojo' | 'gris';

const TONE_BG: Record<Tone, string> = {
  verde: 'bg-emerald-500',
  amarillo: 'bg-amber-500',
  rojo: 'bg-red-500',
  gris: 'bg-muted-foreground/40',
};

function StatusDot({ tone, title, icon }: { tone: Tone; title: string; icon: string }) {
  return (
    <span
      title={title}
      aria-label={title}
      className={cn(
        'inline-flex size-5 items-center justify-center rounded-full text-white',
        TONE_BG[tone],
      )}
    >
      <Icon icon={icon} className="size-3" aria-hidden />
    </span>
  );
}

export function fielTone(e: Empresa): Tone {
  if (!e.metodos.includes('fiel') || !e.vencimiento) return 'gris';
  const s = semaforoVencimiento(e.vencimiento);
  return s ? s.estado : 'gris';
}

export function csfTone(e: Empresa): Tone {
  return e.csf_path ? 'verde' : 'rojo';
}

// Rojo (32-D negativa) requiere parsear el PDF — follow-up.
export function opinionTone(e: Empresa): Tone {
  return e.opinion_path ? 'verde' : 'amarillo';
}

export function EmpresaStatusGroup({ empresa }: { empresa: Empresa }) {
  const fiel = fielTone(empresa);
  const csf = csfTone(empresa);
  const op = opinionTone(empresa);
  const sem = empresa.vencimiento ? semaforoVencimiento(empresa.vencimiento) : null;

  return (
    <div className="flex items-center gap-1.5">
      <StatusDot
        tone={fiel}
        icon="ph:shield-check-light"
        title={fiel === 'gris' ? 'Sin e.firma' : `e.firma: ${sem?.label ?? ''}`}
      />
      <StatusDot
        tone={csf}
        icon="ph:file-text-light"
        title={csf === 'verde' ? 'CSF descargada' : 'CSF pendiente de descarga'}
      />
      <StatusDot
        tone={op}
        icon="ph:clipboard-text-light"
        title={op === 'verde' ? 'Opinión 32-D descargada' : 'Opinión 32-D pendiente'}
      />
      {empresa.metodos.includes('ciec') && (
        <span
          title="CIEC registrada"
          aria-label="CIEC registrada"
          className="inline-flex items-center"
        >
          <Icon icon="ph:key-light" className="size-4 text-muted-foreground/70" />
        </span>
      )}
    </div>
  );
}
