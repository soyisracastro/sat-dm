'use client';

import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

const FMT = new Intl.NumberFormat('es-MX');

/** Entero con separador de miles (es-MX). La DIOT no admite decimales. */
export function formatoEntero(n: number | string | boolean | undefined): string {
  return FMT.format(Number(n ?? 0));
}

/** Parsea lo tecleado a un entero, ignorando separadores y signos. */
export function aEntero(texto: string): number {
  const n = parseInt(texto.replace(/[^\d]/g, ''), 10);
  return Number.isNaN(n) ? 0 : n;
}

interface Props {
  valor: number | string | boolean | undefined;
  onChange: (v: number) => void;
  invalido?: boolean;
  ariaLabel: string;
  className?: string;
}

/** Celda numérica editable con formato de miles, compartida por tabla y drawer. */
export function MontoInput({ valor, onChange, invalido, ariaLabel, className }: Props) {
  return (
    <Input
      inputMode="numeric"
      aria-label={ariaLabel}
      className={cn(
        'h-8 text-right tabular-nums',
        invalido && 'border-destructive focus-visible:ring-destructive',
        className,
      )}
      value={formatoEntero(valor)}
      onChange={(e) => onChange(aEntero(e.target.value))}
      onFocus={(e) => e.currentTarget.select()}
    />
  );
}
