'use client';

import { useState } from 'react';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Icon } from '@/components/ui/icon';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import {
  getRegimenesByTipoPersona,
  type RegimenFiscalCatalogo,
} from '@/lib/fiscal/regimenes-fiscales';
import { tipoPersonaDeRfc } from '@/lib/fiscal/tipo-persona';
import type {
  ActividadEconomicaConfig,
  Empresa,
  EmpresaUpdatePatch,
  RegimenFiscalConfig,
} from '@/lib/types';
import { mensajeDeError } from '@/lib/errores';

interface Props {
  empresa: Empresa;
  onGuardar: (patch: EmpresaUpdatePatch) => Promise<void>;
}

export function ConfiguracionFiscalCard({ empresa, onGuardar }: Props) {
  const [regimenes, setRegimenes] = useState<RegimenFiscalConfig[]>(
    empresa.regimenes_fiscales ?? [],
  );
  const [actividades, setActividades] = useState<ActividadEconomicaConfig[]>(
    empresa.actividades_economicas ?? [],
  );
  const [nuevaActividad, setNuevaActividad] = useState('');
  const [regimenQuery, setRegimenQuery] = useState('');
  const [popoverOpen, setPopoverOpen] = useState(false);

  const [saving, setSaving] = useState(false);
  const [ok, setOk] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const tipo = tipoPersonaDeRfc(empresa.rfc);
  const catalogo = getRegimenesByTipoPersona(tipo);
  const catalogoFiltrado = regimenQuery.trim()
    ? catalogo.filter((r) =>
        (r.clave + ' ' + r.descripcion)
          .toLowerCase()
          .includes(regimenQuery.toLowerCase()),
      )
    : catalogo;
  const seleccionadas = new Set(regimenes.map((r) => r.clave));

  function toggleRegimen(r: RegimenFiscalCatalogo) {
    setOk(false);
    setRegimenes((prev) =>
      prev.some((p) => p.clave === r.clave)
        ? prev.filter((p) => p.clave !== r.clave)
        : [...prev, { clave: r.clave, descripcion: r.descripcion }],
    );
  }

  function quitarRegimen(clave: string) {
    setOk(false);
    setRegimenes((prev) => prev.filter((r) => r.clave !== clave));
  }

  function agregarActividad() {
    const descripcion = nuevaActividad.trim();
    if (!descripcion) return;
    if (
      actividades.some(
        (a) => a.descripcion.toLowerCase() === descripcion.toLowerCase(),
      )
    ) {
      setNuevaActividad('');
      return;
    }
    setOk(false);
    setActividades((prev) => {
      // Si es la primera, queda principal automáticamente.
      const yaHayPrincipal = prev.some((a) => a.principal);
      return [
        ...prev,
        { descripcion, principal: !yaHayPrincipal || prev.length === 0 },
      ];
    });
    setNuevaActividad('');
  }

  function quitarActividad(idx: number) {
    setOk(false);
    setActividades((prev) => {
      const next = prev.filter((_, i) => i !== idx);
      // Si quité la principal y quedan otras, la primera restante toma el lugar.
      if (next.length > 0 && !next.some((a) => a.principal)) {
        next[0] = { ...next[0], principal: true };
      }
      return next;
    });
  }

  function marcarPrincipal(idx: number) {
    setOk(false);
    setActividades((prev) =>
      prev.map((a, i) => ({ ...a, principal: i === idx })),
    );
  }

  async function guardar() {
    setSaving(true);
    setError(null);
    setOk(false);
    try {
      await onGuardar({
        regimenes_fiscales: regimenes,
        actividades_economicas: actividades,
      });
      setOk(true);
    } catch (e) {
      setError(mensajeDeError(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card className="space-y-4 p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon icon="ph:gear-light" className="size-4 text-primary" />
          <span className="text-sm font-medium">Configuración fiscal</span>
        </div>
        {ok && (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-success">
            <Icon icon="ph:check-circle-light" className="size-3.5" /> Guardado
          </span>
        )}
      </div>

      {/* Régimen(es) fiscal(es) */}
      <div className="space-y-2">
        <Label>Régimen(es) fiscal(es)</Label>
        <Popover open={popoverOpen} onOpenChange={setPopoverOpen}>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              className="w-full justify-between font-normal"
              type="button"
            >
              <span className="text-muted-foreground">
                {regimenes.length === 0
                  ? 'Selecciona uno o más regímenes'
                  : `${regimenes.length} régimen${regimenes.length === 1 ? '' : 'es'} seleccionado${regimenes.length === 1 ? '' : 's'}`}
              </span>
              <Icon icon="ph:caret-down-light" className="size-4" />
            </Button>
          </PopoverTrigger>
          <PopoverContent
            className="w-[--radix-popover-trigger-width] p-0"
            align="start"
          >
            <div className="border-b p-2">
              <Input
                placeholder="Buscar régimen…"
                value={regimenQuery}
                onChange={(e) => setRegimenQuery(e.target.value)}
                className="h-8"
                autoFocus
              />
            </div>
            <div className="max-h-64 overflow-y-auto py-1">
              {catalogoFiltrado.length === 0 ? (
                <div className="px-3 py-2 text-xs text-muted-foreground">
                  Sin coincidencias.
                </div>
              ) : (
                catalogoFiltrado.map((r) => {
                  const seleccionado = seleccionadas.has(r.clave);
                  return (
                    <button
                      key={r.clave}
                      type="button"
                      onClick={() => toggleRegimen(r)}
                      className={cn(
                        'flex w-full items-start gap-2 px-3 py-2 text-left text-sm hover:bg-muted/50',
                        seleccionado && 'bg-muted/30',
                      )}
                    >
                      <Icon
                        icon={
                          seleccionado
                            ? 'ph:check-square-light'
                            : 'ph:square-light'
                        }
                        className={cn(
                          'size-4 shrink-0 translate-y-0.5',
                          seleccionado ? 'text-primary' : 'text-muted-foreground',
                        )}
                      />
                      <span className="min-w-0">
                        <span className="font-mono text-xs text-muted-foreground">
                          {r.clave}
                        </span>{' '}
                        <span>{r.descripcion}</span>
                      </span>
                    </button>
                  );
                })
              )}
            </div>
          </PopoverContent>
        </Popover>

        {regimenes.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {regimenes.map((r) => (
              <Badge
                key={r.clave}
                variant="secondary"
                className="gap-1 pr-1"
              >
                <span className="font-mono text-[10px]">{r.clave}</span>
                <span>{r.descripcion}</span>
                <button
                  type="button"
                  onClick={() => quitarRegimen(r.clave)}
                  className="ml-1 rounded-sm p-0.5 hover:bg-muted-foreground/20"
                  aria-label={`Quitar régimen ${r.clave}`}
                >
                  <Icon icon="ph:x-light" className="size-3" />
                </button>
              </Badge>
            ))}
          </div>
        )}
      </div>

      <Separator />

      {/* Actividad(es) económica(s) */}
      <div className="space-y-2">
        <Label htmlFor="nueva-actividad">Actividad(es) económica(s)</Label>
        <p className="text-xs text-muted-foreground">
          Describe cada actividad. Marca una como principal (la que el SAT
          considera la actividad preponderante).
        </p>
        <div className="flex gap-2">
          <Input
            id="nueva-actividad"
            placeholder="Ej. Comercio al por menor de abarrotes"
            value={nuevaActividad}
            onChange={(e) => setNuevaActividad(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                agregarActividad();
              }
            }}
          />
          <Button
            type="button"
            variant="outline"
            onClick={agregarActividad}
            disabled={!nuevaActividad.trim()}
          >
            <Icon icon="ph:plus-light" className="size-4" />
            Agregar
          </Button>
        </div>

        {actividades.length > 0 && (
          <ul className="space-y-1 pt-1">
            {actividades.map((a, idx) => (
              <li
                key={`${a.descripcion}-${idx}`}
                className="flex items-start gap-2 rounded-md border bg-card px-2 py-1.5"
              >
                <button
                  type="button"
                  onClick={() => marcarPrincipal(idx)}
                  className="mt-0.5 shrink-0"
                  title={a.principal ? 'Es la actividad principal' : 'Marcar como principal'}
                  aria-pressed={a.principal}
                >
                  <Icon
                    icon={
                      a.principal
                        ? 'ph:radio-button-light'
                        : 'ph:circle-light'
                    }
                    className={cn(
                      'size-4',
                      a.principal ? 'text-primary' : 'text-muted-foreground',
                    )}
                  />
                </button>
                <span className="min-w-0 flex-1 text-sm">
                  {a.descripcion}
                  {a.principal && (
                    <span className="ml-2 text-[10px] font-semibold uppercase tracking-wide text-primary">
                      Principal
                    </span>
                  )}
                </span>
                <button
                  type="button"
                  onClick={() => quitarActividad(idx)}
                  className="rounded-sm p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                  aria-label={`Quitar actividad ${a.descripcion}`}
                >
                  <Icon icon="ph:x-light" className="size-3.5" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div>
        <Button onClick={guardar} disabled={saving}>
          {saving ? (
            <Icon icon="ph:circle-notch-light" className="size-4 animate-spin" />
          ) : (
            <Icon icon="ph:check-light" className="size-4" />
          )}
          Guardar configuración
        </Button>
      </div>
    </Card>
  );
}
