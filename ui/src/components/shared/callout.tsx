import type { ReactNode } from 'react';

import { Icon } from '@/components/ui/icon';

interface CalloutProps {
  icon: string;
  title: string;
  text: string;
  /** Acción a la derecha (típicamente un Button asChild → Link). */
  action?: ReactNode;
}

/**
 * Callout de sugerencia/atajo con el azul de acento del design system: fondo
 * `accent`, cuadro de icono `primary`. Se usa para los cruces entre descarga
 * masiva (Web Service) y descarga rápida (portal).
 */
export function Callout({ icon, title, text, action }: CalloutProps) {
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-primary/20 bg-accent px-4.5 py-4 sm:flex-row sm:items-center sm:justify-between dark:border-border">
      <div className="flex min-w-0 items-center gap-3.5">
        <span className="flex size-9.5 shrink-0 items-center justify-center rounded-[10px] bg-primary text-primary-foreground shadow-sm">
          <Icon icon={icon} className="size-4.75" />
        </span>
        <div className="min-w-0">
          <div className="text-sm font-bold tracking-tight text-foreground">
            {title}
          </div>
          <p className="mt-0.5 max-w-prose text-xs leading-relaxed text-foreground/70">
            {text}
          </p>
        </div>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
