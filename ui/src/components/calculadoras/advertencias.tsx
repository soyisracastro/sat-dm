import { Icon } from '@/components/ui/icon';

/** Lista de advertencias del backend en ámbar. No renderiza nada si está vacía. */
export function Advertencias({ advertencias }: { advertencias: string[] }) {
  if (!advertencias || advertencias.length === 0) return null;
  return (
    <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-800 dark:text-amber-300">
      <div className="flex gap-2">
        <Icon icon="ph:warning-light" className="mt-0.5 size-4 shrink-0" />
        <ul className="min-w-0 space-y-1">
          {advertencias.map((a) => (
            <li key={a}>{a}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
