'use client';

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

const MESES = [
  'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
] as const;

interface Props {
  /** Periodo seleccionado, formato YYYY-MM. */
  periodo: string;
  onChange: (periodo: string) => void;
  disabled?: boolean;
}

/** Selector de mes/año del periodo a declarar (DIOT es mensual, 2025+). */
export function SelectorPeriodo({ periodo, onChange, disabled }: Props) {
  const [anio, mes] = periodo.split('-');
  const anioActual = new Date().getFullYear();
  // La nueva plataforma aplica para ejercicios 2025 en adelante.
  const anios = Array.from({ length: anioActual - 2025 + 1 }, (_, i) => String(2025 + i));

  return (
    <div className="flex items-center gap-2">
      <Select
        value={mes}
        onValueChange={(m) => onChange(`${anio}-${m}`)}
        disabled={disabled}
      >
        <SelectTrigger className="w-36" aria-label="Mes">
          <SelectValue placeholder="Mes" />
        </SelectTrigger>
        <SelectContent>
          {MESES.map((nombre, i) => {
            const valor = String(i + 1).padStart(2, '0');
            return (
              <SelectItem key={valor} value={valor}>
                {nombre}
              </SelectItem>
            );
          })}
        </SelectContent>
      </Select>
      <Select
        value={anio}
        onValueChange={(a) => onChange(`${a}-${mes}`)}
        disabled={disabled}
      >
        <SelectTrigger className="w-24" aria-label="Año">
          <SelectValue placeholder="Año" />
        </SelectTrigger>
        <SelectContent>
          {anios.map((a) => (
            <SelectItem key={a} value={a}>
              {a}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
