import { cn } from '@/lib/utils';
import { tipoPersona } from '@/lib/empresa-visual';

/**
 * Badge "Moral"/"Física" derivado del RFC (12 = PM, 13 = PF). Tonos de la
 * paleta de datos del boceto: violeta para morales, cian para físicas.
 */
export function EmpresaTipoBadge({ rfc }: { rfc: string }) {
  const tipo = tipoPersona(rfc);
  return (
    <span
      className={cn(
        'inline-flex rounded-md px-2 py-0.5 text-[11px] font-semibold',
        tipo === 'PM'
          ? 'bg-violet-600/15 text-violet-700 dark:text-violet-300'
          : 'bg-cyan-600/15 text-cyan-700 dark:text-cyan-300',
      )}
    >
      {tipo === 'PM' ? 'Moral' : 'Física'}
    </span>
  );
}
