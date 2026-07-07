'use client';

import { Button } from '@/components/ui/button';
import { Icon } from '@/components/ui/icon';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { NIVELES_CUSTOM } from '@/lib/constants';

const MAX_NIVELES = 6;

interface EstructuraCustomBuilderProps {
  /** Tokens en orden, de la carpeta raíz hacia adentro. */
  niveles: string[];
  onChange: (niveles: string[]) => void;
}

/**
 * Builder de la estructura personalizada del organizador: lista ordenada de
 * niveles (uno por carpeta) con variables del CFDI, reordenables con flechas,
 * y vista previa en vivo del path resultante.
 */
export function EstructuraCustomBuilder({
  niveles,
  onChange,
}: EstructuraCustomBuilderProps) {
  function cambiar(idx: number, valor: string) {
    onChange(niveles.map((n, i) => (i === idx ? valor : n)));
  }

  function mover(idx: number, delta: -1 | 1) {
    const destino = idx + delta;
    if (destino < 0 || destino >= niveles.length) return;
    const copia = [...niveles];
    [copia[idx], copia[destino]] = [copia[destino], copia[idx]];
    onChange(copia);
  }

  function quitar(idx: number) {
    if (niveles.length <= 1) return;
    onChange(niveles.filter((_, i) => i !== idx));
  }

  function agregar() {
    if (niveles.length >= MAX_NIVELES) return;
    // Sugerir la primera variable aún no usada (repetir es válido pero raro).
    const libre = NIVELES_CUSTOM.find((n) => !niveles.includes(n.value));
    onChange([...niveles, libre?.value ?? NIVELES_CUSTOM[0].value]);
  }

  const preview = niveles
    .map((v) => NIVELES_CUSTOM.find((n) => n.value === v)?.ejemplo ?? v)
    .join('/');

  return (
    <div className="space-y-3 rounded-md border p-4">
      <Label>Niveles de carpetas (de afuera hacia adentro)</Label>

      <div className="space-y-2">
        {niveles.map((nivel, idx) => (
          <div key={idx} className="flex items-center gap-2">
            <span className="w-4 text-right text-xs text-muted-foreground">
              {idx + 1}.
            </span>
            <Select value={nivel} onValueChange={(v) => cambiar(idx, v)}>
              <SelectTrigger className="w-full max-w-64">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {NIVELES_CUSTOM.map((n) => (
                  <SelectItem key={n.value} value={n.value}>
                    {n.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              disabled={idx === 0}
              onClick={() => mover(idx, -1)}
              title="Subir nivel"
            >
              <Icon icon="ph:arrow-up-light" className="size-4" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              disabled={idx === niveles.length - 1}
              onClick={() => mover(idx, 1)}
              title="Bajar nivel"
            >
              <Icon icon="ph:arrow-down-light" className="size-4" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              disabled={niveles.length <= 1}
              onClick={() => quitar(idx)}
              title="Quitar nivel"
            >
              <Icon icon="ph:x-light" className="size-4" />
            </Button>
          </div>
        ))}
      </div>

      {niveles.length < MAX_NIVELES && (
        <Button type="button" variant="outline" size="sm" onClick={agregar}>
          <Icon icon="ph:plus-light" className="size-4" />
          Agregar nivel
        </Button>
      )}

      <p className="text-xs text-muted-foreground">
        Vista previa:{' '}
        <span className="font-mono text-foreground">{preview}</span>
      </p>
    </div>
  );
}
