'use client';

import { useAuth } from '@/providers/auth-provider';
import { Badge } from '@/components/ui/badge';
import { Icon } from '@/components/ui/icon';

/**
 * Badge pequeño "🌟 Fundador" que se renderea junto al avatar/email del
 * usuario en el header. Solo visible si `is_founder=true`.
 */
export function FounderBadge() {
  const { license } = useAuth();
  if (!license?.is_founder) return null;
  return (
    <Badge
      variant="secondary"
      className="bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300 gap-1"
      title={
        license.founder_acquired_at
          ? `Fundador desde ${new Date(license.founder_acquired_at).toLocaleDateString('es-MX')}`
          : 'Contador Fundador de TodoConta'
      }
    >
      <Icon icon="ph:star-fill" className="size-3" />
      Fundador
    </Badge>
  );
}
