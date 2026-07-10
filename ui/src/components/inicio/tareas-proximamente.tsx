import { Badge } from '@/components/ui/badge';
import { Icon } from '@/components/ui/icon';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Placeholder del bloque "Tareas de hoy" del Panel Ejecutivo. La sección de
// Tareas (pendientes fiscales por empresa + sugerencias automáticas) aún no
// existe; este componente reserva su lugar con la estructura visual del
// diseño (lista a la izquierda, contadores y sugerencias a la derecha) en
// estado deshabilitado. Cuando Tareas se implemente, se sustituye completo
// por el bloque real con datos.
// ---------------------------------------------------------------------------

/** Fila fantasma: silueta de una tarea (checkbox + título + chips + fecha). */
function FilaFantasma({ ancho }: { ancho: string }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border/70 bg-secondary/40 px-4 py-3">
      <span className="size-5 shrink-0 rounded-full border-[1.5px] border-input/70" />
      <div className="min-w-0 flex-1 space-y-2">
        <div className={cn('h-2.5 rounded-full bg-input/50', ancho)} />
        <div className="flex items-center gap-2">
          <div className="h-2 w-24 rounded-full bg-input/35" />
          <div className="h-2 w-14 rounded-full bg-input/35" />
        </div>
      </div>
      <div className="h-2 w-12 shrink-0 rounded-full bg-input/35" />
    </div>
  );
}

function Contador({ etiqueta }: { etiqueta: string }) {
  return (
    <div className="rounded-lg border bg-card p-3">
      <div className="text-[22px] font-extrabold leading-none tracking-tight text-muted-foreground/40">
        —
      </div>
      <div className="mt-1.5 text-[11px] text-muted-foreground">{etiqueta}</div>
    </div>
  );
}

export function TareasProximamente() {
  return (
    <section className="rounded-xl border bg-card p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-sm font-bold tracking-tight">
          <Icon
            icon="ph:clipboard-text-light"
            className="size-4 shrink-0 text-muted-foreground"
          />
          Tareas de hoy
          <Badge variant="secondary" className="text-[10px]">
            Próximamente
          </Badge>
        </h2>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div aria-hidden className="select-none space-y-2">
          <FilaFantasma ancho="w-3/5" />
          <FilaFantasma ancho="w-2/5" />
          <FilaFantasma ancho="w-1/2" />
        </div>

        <div className="flex flex-col gap-4">
          <div aria-hidden className="grid select-none grid-cols-3 gap-2.5">
            <Contador etiqueta="Vencidas" />
            <Contador etiqueta="Para hoy" />
            <Contador etiqueta="Esta semana" />
          </div>
          <div className="border-t border-border/70 pt-3.5">
            <div className="flex items-center gap-1.5 text-xs font-bold">
              <Icon icon="ph:sparkle-light" className="size-3.5 text-accent-ai" />
              Sugerencias de TodoConta
            </div>
            <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
              Aquí vivirán tus pendientes fiscales por empresa, con
              recordatorios de vencimientos y sugerencias automáticas.
              Disponible próximamente.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
