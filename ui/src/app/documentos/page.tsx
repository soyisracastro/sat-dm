'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

import { Icon } from '@/components/ui/icon';

import { useServer } from '@/providers/server-provider';
import { useEmpresas } from '@/hooks/use-empresas';
import { useCiecJob } from '@/hooks/use-ciec-job';
import { PageHeading } from '@/components/layout/page-heading';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { CaptchaModal } from '@/components/descarga/captcha-modal';
import { JobProgress } from '@/components/descarga/job-progress';

export default function DocumentosPage() {
  const { apiClient } = useServer();
  const { empresas } = useEmpresas();
  const job = useCiecJob();

  const [rfc, setRfc] = useState('');
  useEffect(() => {
    if (!rfc && empresas.length > 0) {
      setRfc((empresas.find((e) => e.default) ?? empresas[0]).rfc);
    }
  }, [empresas, rfc]);

  const empresa = empresas.find((e) => e.rfc === rfc);
  const tieneCiec = !!empresa?.metodos.includes('ciec');
  const corriendo =
    job.estado !== 'idle' && job.estado !== 'done'
    && job.estado !== 'error' && job.estado !== 'cancelled';

  function bajar(kind: 'constancia' | 'opinion') {
    if (!empresa || !tieneCiec || corriendo) return;
    job.iniciar(
      () =>
        kind === 'constancia'
          ? apiClient.ciecConstancia({ rfc: empresa.rfc })
          : apiClient.ciecOpinion({ rfc: empresa.rfc }),
      { rfc: empresa.rfc },
    );
  }

  return (
    <div className="max-w-2xl space-y-6">
      <PageHeading
        title="Documentos"
        description="Descarga la Constancia de Situación Fiscal y la Opinión de Cumplimiento 32-D (PDF) del portal del SAT."
      />

      {empresas.length === 0 ? (
        <Alert>
          <AlertDescription>
            No tienes empresas registradas.{' '}
            <Link href="/empresas" className="font-medium text-primary underline">
              Agrega una en Empresas
            </Link>
            .
          </AlertDescription>
        </Alert>
      ) : (
        <Card className="space-y-4 p-5">
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
            {empresa && !tieneCiec && (
              <p className="text-xs text-amber-600">
                Esta empresa no tiene CIEC registrada. Agrégala en Empresas para
                descargar documentos por el portal.
              </p>
            )}
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <DocCard
              icon={<Icon icon="ph:file-text-light" className="size-5 text-primary" />}
              title="Constancia de Situación Fiscal"
              desc="Tu CSF en PDF."
              disabled={!tieneCiec || corriendo}
              onClick={() => bajar('constancia')}
            />
            <DocCard
              icon={<Icon icon="ph:scroll-light" className="size-5 text-primary" />}
              title="Opinión de Cumplimiento 32-D"
              desc="Tu opinión 32-D en PDF."
              disabled={!tieneCiec || corriendo}
              onClick={() => bajar('opinion')}
            />
          </div>
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

function DocCard({
  icon,
  title,
  desc,
  disabled,
  onClick,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border p-4">
      {icon}
      <div className="space-y-0.5">
        <div className="text-sm font-medium leading-tight">{title}</div>
        <div className="text-xs text-muted-foreground">{desc}</div>
      </div>
      <Button size="sm" className="mt-1 w-full" disabled={disabled} onClick={onClick}>
        Descargar
      </Button>
    </div>
  );
}
