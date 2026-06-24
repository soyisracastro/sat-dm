import Image from 'next/image';

import { cn } from '@/lib/utils';

interface BrandMarkProps {
  /** Tamaño del icono en px. Default 34. */
  size?: number;
  /** Tamaño tipográfico del wordmark en px. Default 17. */
  wordmarkSize?: number;
  /** Oculta el wordmark; deja solo el icono (sidebar colapsado). */
  iconOnly?: boolean;
  /** `priority` de next/image (above-the-fold, p. ej. login). */
  priority?: boolean;
  /** Clases del wrapper (p. ej. `flex-1` en el sidebar). */
  className?: string;
  /** Clases del icono (radio/sombra). */
  iconClassName?: string;
}

/**
 * Lockup de marca TodoConta: icono + wordmark con el punto en cian (`--accent-ai`),
 * igual que el BrandMark canónico de todoconta-apps. Reutilizable (sidebar, login, …).
 */
export function BrandMark({
  size = 34,
  wordmarkSize = 17,
  iconOnly = false,
  priority = false,
  className,
  iconClassName = 'rounded-lg shadow-sm',
}: BrandMarkProps) {
  return (
    <span className={cn('inline-flex items-center gap-2.5', className)}>
      <Image
        src="/todoconta-icon.svg"
        alt="TodoConta"
        width={size}
        height={size}
        priority={priority}
        className={cn('shrink-0', iconClassName)}
      />
      {!iconOnly && (
        <span
          className="truncate font-extrabold tracking-tight text-foreground"
          style={{ fontSize: wordmarkSize }}
        >
          TodoConta<span className="text-accent-ai">.</span>
        </span>
      )}
    </span>
  );
}
