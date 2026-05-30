'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';

import { Icon } from '@/components/ui/icon';

import { useServer } from '@/providers/server-provider';
import { useEmpresas } from '@/hooks/use-empresas';
import { useCiecJob } from '@/hooks/use-ciec-job';
import { PageHeading } from '@/components/layout/page-heading';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { CaptchaModal } from '@/components/descarga/captcha-modal';
import { JobProgress } from '@/components/descarga/job-progress';
import { metodoPortalPreferido, etiquetaMetodo } from '@/lib/empresa-metodo';

const TIPOS = [
  { value: 'R', label: 'Recibidos' },
  { value: 'E', label: 'Emitidos' },
  { value: 'RE', label: 'Ambos' },
] as const;

function ymd(d: Date) {
  return d.toISOString().slice(0, 10);
}

export default function NuevaDescargaPage() {
  const { apiClient } = useServer();
  const { empresas } = useEmpresas();
  const job = useCiecJob();

  const hoy = useMemo(() => new Date(), []);
  const [rfc, setRfc] = useState('');
  const [tipo, setTipo] = useState<'R' | 'E' | 'RE'>('RE');
  const [desde, setDesde] = useState(ymd(new Date(hoy.getFullYear(), hoy.getMonth(), 1)));
  const [hasta, setHasta] = useState(ymd(new Date(hoy.getFullYear(), hoy.getMonth() + 1, 0)));

  // Preseleccionar la empresa activa (o la primera) cuando carga el catálogo.
  useEffect(() => {
    if (!rfc && empresas.length > 0) {
      setRfc((empresas.find((e) => e.default) ?? empresas[0]).rfc);
    }
  }, [empresas, rfc]);

  const empresa = empresas.find((e) => e.rfc === rfc);
  const metodo = metodoPortalPreferido(empresa);
  const corriendo = job.estado !== 'idle' && job.estado !== 'done'
    && job.estado !== 'error' && job.estado !== 'cancelled';

  function iniciar() {
    if (!empresa || !metodo) return;
    if (metodo === 'fiel') {
      job.iniciar(
        () =>
          apiClient.cfdiFiel({
            fecha_inicio: desde,
            fecha_fin: hasta,
            tipo_comprobante: tipo,
          }),
        { rfc: empresa.rfc },
      );
    } else {
      job.iniciar(
        () =>
          apiClient.ciecCfdi({
            rfc: empresa.rfc,
            fecha_inicio: desde,
            fecha_fin: hasta,
            tipo_comprobante: tipo,
          }),
        { rfc: empresa.rfc },
      );
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <PageHeading
        title="Nueva descarga"
        description="Descarga CFDIs del portal del SAT. Si la empresa tiene e.firma se usa esa (sin captcha); si no, CIEC."
      />

      {empresas.length === 0 ? (
        <Alert>
          <AlertDescription>
            No tienes empresas registradas.{' '}
            <Link href="/empresas" className="font-medium text-primary underline">
              Agrega una en Empresas
            </Link>{' '}
            para descargar.
          </AlertDescription>
        </Alert>
      ) : (
        <Card className="space-y-4 p-5">
          {/* Empresa */}
          <div className="space-y-2">
            <Label htmlFor="empresa">Empresa</Label>
            <select
              id="empresa"
              value={rfc}
              onChange={(e) => setRfc(e.target.value)}
              disabled={corriendo}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs"
            >
              {empresas.map((e) => (
                <option key={e.rfc} value={e.rfc}>
                  {e.nombre} · {e.rfc}
                </option>
              ))}
            </select>
            {empresa && !metodo && (
              <p className="text-xs text-amber-600">
                Esta empresa no tiene e.firma ni CIEC. Agrégala en Empresas o usa la
                descarga por Web Service.
              </p>
            )}
          </div>

          {/* Tipo */}
          <div className="space-y-2">
            <Label>Tipo de comprobante</Label>
            <div className="flex gap-2">
              {TIPOS.map((t) => (
                <Button
                  key={t.value}
                  type="button"
                  variant={tipo === t.value ? 'default' : 'outline'}
                  size="sm"
                  disabled={corriendo}
                  onClick={() => setTipo(t.value)}
                >
                  {t.label}
                </Button>
              ))}
            </div>
          </div>

          {/* Periodo */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="desde">Desde</Label>
              <Input id="desde" type="date" value={desde} disabled={corriendo}
                     onChange={(e) => setDesde(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="hasta">Hasta</Label>
              <Input id="hasta" type="date" value={hasta} disabled={corriendo}
                     onChange={(e) => setHasta(e.target.value)} />
            </div>
          </div>

          {metodo && (
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Icon
                icon={metodo === 'fiel' ? 'ph:shield-check-light' : 'ph:key-light'}
                className="size-3.5"
              />
              Usando: {etiquetaMetodo(metodo)}
            </div>
          )}

          <Button onClick={iniciar} disabled={!metodo || corriendo} className="w-full">
            <Icon
              icon={metodo === 'fiel' ? 'ph:shield-check-light' : 'ph:key-light'}
              className="size-4"
            />
            Iniciar descarga
          </Button>
        </Card>
      )}

      <JobProgress
        estado={job.estado}
        log={job.log}
        resultado={job.resultado}
        error={job.error}
      />

      <CaptchaModal captcha={job.captcha} onResolver={job.responderCaptcha} />
    </div>
  );
}
