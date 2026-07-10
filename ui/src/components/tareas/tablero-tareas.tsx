'use client';

import { Icon } from '@/components/ui/icon';
import { infoVence } from '@/lib/tareas';
import type { Empresa, Tarea, TareaEstado } from '@/lib/types';
import { cn } from '@/lib/utils';
import { EmpresaChip, TipoTareaTag } from '@/components/tareas/tarea-row';

const COLUMNAS: { estado: TareaEstado; label: string; dotClass: string }[] = [
  { estado: 'pendiente', label: 'Por hacer', dotClass: 'bg-muted-foreground/50' },
  { estado: 'curso', label: 'En curso', dotClass: 'bg-primary' },
  { estado: 'hecho', label: 'Hechas', dotClass: 'bg-success' },
];

interface TableroTareasProps {
  tareas: Tarea[];
  empresas: Empresa[];
  onEdit: (tarea: Tarea) => void;
}

/** Vista tablero: 3 columnas por estado; clic en la card abre el drawer. */
export function TableroTareas({ tareas, empresas, onEdit }: TableroTareasProps) {
  return (
    <div className="grid grid-cols-1 items-start gap-3.5 md:grid-cols-3">
      {COLUMNAS.map((col) => {
        const items = tareas.filter((t) => t.estado === col.estado);
        return (
          <div
            key={col.estado}
            className="flex min-h-[120px] flex-col gap-2.5 rounded-xl bg-secondary p-3"
          >
            <div className="flex items-center gap-2 px-1">
              <span className={cn('size-2 rounded-full', col.dotClass)} />
              <span className="text-[12.5px] font-bold">{col.label}</span>
              <span className="ml-auto font-mono text-[11px] font-bold text-muted-foreground">
                {items.length}
              </span>
            </div>
            {items.length === 0 && (
              <div className="py-4 text-center text-xs text-muted-foreground/70">
                Nada aquí
              </div>
            )}
            {items.map((t) => {
              const hecha = t.estado === 'hecho';
              const vence = infoVence(t.fecha);
              return (
                <div
                  key={t.id}
                  role="button"
                  tabIndex={0}
                  title="Clic para editar"
                  onClick={() => onEdit(t)}
                  onKeyDown={(e) => e.key === 'Enter' && onEdit(t)}
                  className={cn(
                    'flex cursor-pointer flex-col gap-2 rounded-lg border border-t-[3px] bg-card p-3 transition-shadow hover:shadow-sm',
                    t.prioridad === 'alta' && !hecha
                      ? 'border-t-destructive'
                      : t.prioridad === 'media' && !hecha
                        ? 'border-t-warning'
                        : 'border-t-transparent',
                  )}
                >
                  <div
                    className={cn(
                      'text-[12.5px] font-semibold leading-snug',
                      hecha && 'text-muted-foreground line-through decoration-muted-foreground/50',
                    )}
                  >
                    {t.titulo}
                  </div>
                  <EmpresaChip rfc={t.rfc} empresas={empresas} />
                  <div className="flex items-center gap-2">
                    <TipoTareaTag tipo={t.tipo} />
                    {!hecha && (
                      <span
                        className={cn(
                          'ml-auto inline-flex items-center gap-1 text-[11px] font-semibold',
                          vence.tono === 'rojo' && 'text-destructive',
                          vence.tono === 'ambar' && 'text-warning',
                          vence.tono === 'normal' && 'text-muted-foreground',
                        )}
                      >
                        <Icon icon={vence.icono} className="size-3" />
                        {vence.texto}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}
