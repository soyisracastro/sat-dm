import { cn } from '@/lib/utils';
import { colorEmpresa, tipoPersona } from '@/lib/empresa-visual';

/** Cuadro PF/PM con el color determinista de la empresa. */
export function EmpresaBadge({
  rfc,
  size = 'md',
}: {
  rfc: string;
  size?: 'sm' | 'md';
}) {
  return (
    <span
      className={cn(
        'flex shrink-0 items-center justify-center rounded-md font-mono font-bold text-white',
        size === 'md' ? 'size-8 text-[11px]' : 'size-6.5 rounded text-[10px]',
      )}
      style={{ background: colorEmpresa(rfc) }}
    >
      {tipoPersona(rfc)}
    </span>
  );
}
