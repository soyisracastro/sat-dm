'use client';

import { useEffect, useState } from 'react';

import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

const formateador = new Intl.NumberFormat('es-MX', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function parsearMoneda(texto: string): number | null {
  const limpio = texto.replace(/[$,\s]/g, '');
  if (limpio === '' || limpio === '-' || limpio === '.') return null;
  const n = Number(limpio);
  return Number.isFinite(n) ? n : null;
}

interface MonedaInputProps {
  id?: string;
  /** Monto en pesos; null = campo vacío. */
  value: number | null;
  onChange: (valor: number | null) => void;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
  'aria-label'?: string;
}

/**
 * Input de montos en pesos: prefijo `$`, formateo es-MX al perder el foco y
 * valor crudo mientras se edita. Emite `null` cuando el campo queda vacío.
 */
export function MonedaInput({
  id,
  value,
  onChange,
  disabled,
  placeholder,
  className,
  'aria-label': ariaLabel,
}: MonedaInputProps) {
  const [texto, setTexto] = useState(() =>
    value == null ? '' : formateador.format(value),
  );
  const [enfocado, setEnfocado] = useState(false);

  // Fuera de foco el texto sigue al valor controlado (formateado es-MX).
  useEffect(() => {
    if (!enfocado) setTexto(value == null ? '' : formateador.format(value));
  }, [value, enfocado]);

  return (
    <div className="relative">
      <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-sm text-muted-foreground">
        $
      </span>
      <Input
        id={id}
        type="text"
        inputMode="decimal"
        aria-label={ariaLabel}
        disabled={disabled}
        placeholder={placeholder ?? '0.00'}
        className={cn('pl-7 text-right tabular-nums', className)}
        value={texto}
        onFocus={() => {
          setEnfocado(true);
          // Editar sobre el valor crudo (y vacío si aún no hay monto).
          setTexto(value == null || value === 0 ? '' : String(value));
        }}
        onBlur={() => setEnfocado(false)}
        onChange={(e) => {
          setTexto(e.target.value);
          onChange(parsearMoneda(e.target.value));
        }}
      />
    </div>
  );
}
