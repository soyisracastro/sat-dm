// ---------------------------------------------------------------------------
// Validation progress indicator
// ---------------------------------------------------------------------------

interface ValidacionProgressProps {
  progress: number; // 0–100
  total: number;
}

export function ValidacionProgress({ progress, total }: ValidacionProgressProps) {
  const verified = Math.round((progress / 100) * total);

  return (
    <div className="space-y-2">
      {/* Progress bar */}
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-all duration-300 ease-out"
          style={{ width: `${Math.min(progress, 100)}%` }}
        />
      </div>

      {/* Text */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>Validando... {progress}%</span>
        <span>
          {verified} de {total} verificados
        </span>
      </div>
    </div>
  );
}
