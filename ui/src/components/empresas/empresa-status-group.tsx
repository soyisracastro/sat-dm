import { Icon } from '@/components/ui/icon';
import { cn } from '@/lib/utils';
import { semaforoVencimiento } from '@/lib/vencimiento';
import type { Empresa } from '@/lib/types';

type Tone = 'verde' | 'amarillo' | 'rojo' | 'gris';

// Chips estilo boceto v2: fondo suave del tono + icono en color (no sólido).
const TONE_CHIP: Record<Tone, string> = {
  verde: 'bg-emerald-500/12 text-emerald-600 dark:text-emerald-400',
  amarillo: 'bg-amber-500/15 text-amber-600 dark:text-amber-400',
  rojo: 'bg-red-500/12 text-red-600 dark:text-red-400',
  gris: 'bg-secondary text-muted-foreground/60',
};

function StatusDot({ tone, title, icon }: { tone: Tone; title: string; icon: string }) {
  return (
    <span
      title={title}
      aria-label={title}
      className={cn(
        'inline-flex size-6 items-center justify-center rounded-md',
        TONE_CHIP[tone],
      )}
    >
      <Icon icon={icon} className="size-3.5" aria-hidden />
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
      {/* Empresa importada por sync (existe en tu otra instalación): aquí
          todavía no hay credenciales — captúralas para operar en este lado. */}
      {empresa.metodos.length === 0 && (empresa.metodos_sync?.length ?? 0) > 0 && (
        <span
          title="Sincronizada desde tu otra instalación: captura aquí su e.firma o CIEC para usarla"
          className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-800 dark:bg-amber-900/30 dark:text-amber-400"
        >
          <Icon icon="ph:key-light" className="size-3" />
          Requiere credenciales aquí
        </span>
      )}
    </div>
  );
}
