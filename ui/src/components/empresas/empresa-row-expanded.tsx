'use client';

import { useEffect } from 'react';

import { useServer } from '@/providers/server-provider';
import { useCiecJob } from '@/hooks/use-ciec-job';
import { Icon } from '@/components/ui/icon';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { CaptchaModal } from '@/components/descarga/captcha-modal';
import { JobProgress } from '@/components/descarga/job-progress';
import { semaforoVencimiento } from '@/lib/vencimiento';
import type { Empresa } from '@/lib/types';

interface Props {
  empresa: Empresa;
  /** Llamado cuando termina un job exitoso, para que el padre refresque el semáforo. */
  onJobDone: () => void;
}

function formatoFecha(iso: string | null | undefined): string | null {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleString('es-MX');
  } catch {
    return iso;
  }
}

export function EmpresaRowExpanded({ empresa, onJobDone }: Props) {
  const { apiClient } = useServer();
  const job = useCiecJob();
  const sem = empresa.vencimiento ? semaforoVencimiento(empresa.vencimiento) : null;
  const tieneFiel = empresa.metodos.includes('fiel');
  const tieneCiec = empresa.metodos.includes('ciec');
  const corriendo =
    job.estado !== 'idle' &&
    job.estado !== 'done' &&
    job.estado !== 'error' &&
    job.estado !== 'cancelled';

  useEffect(() => {
    if (job.estado === 'done') onJobDone();
  }, [job.estado, onJobDone]);

  function bajar(kind: 'constancia' | 'opinion') {
    if (!tieneCiec || corriendo) return;
    job.iniciar(
      () =>
        kind === 'constancia'
          ? apiClient.ciecConstancia({ rfc: empresa.rfc })
          : apiClient.ciecOpinion({ rfc: empresa.rfc }),
      { rfc: empresa.rfc },
    );
  }

  return (
    <div className="space-y-3">
      <div className="grid gap-4 sm:grid-cols-3">
        {/* FIEL (info, sin descarga) */}
        <section className="space-y-1 text-xs">
          <div className="flex items-center gap-1.5 font-medium text-foreground">
            <Icon icon="ph:shield-check-light" className="size-3.5" />
            e.firma
          </div>
          {tieneFiel && sem ? (
            <>
              <div>Vence: {sem.fecha}</div>
              <div className="text-muted-foreground">{sem.label}</div>
            </>
          ) : (
            <div className="text-muted-foreground">Sin e.firma registrada</div>
          )}
        </section>

        {/* Constancia de Situación Fiscal */}
        <section className="space-y-2 text-xs">
          <div className="flex items-center gap-1.5 font-medium text-foreground">
            <Icon icon="ph:file-text-light" className="size-3.5" />
            Constancia de Situación Fiscal
          </div>
          {empresa.csf_descargada_en && (
            <div className="text-muted-foreground">
              Última descarga: {formatoFecha(empresa.csf_descargada_en)}
            </div>
          )}
          <Button
            size="sm"
            variant="outline"
            disabled={!tieneCiec || corriendo}
            onClick={() => bajar('constancia')}
          >
            <Icon icon="ph:download-simple-light" className="mr-1.5 size-3.5" />
            {empresa.csf_path ? 'Volver a descargar' : 'Descargar CSF'}
          </Button>
          {!tieneCiec && (
            <p className="text-muted-foreground">Requiere CIEC registrada.</p>
          )}
        </section>

        {/* Opinión de Cumplimiento 32-D */}
        <section className="space-y-2 text-xs">
          <div className="flex items-center gap-1.5 font-medium text-foreground">
            <Icon icon="ph:clipboard-text-light" className="size-3.5" />
            Opinión de Cumplimiento 32-D
          </div>
          {empresa.opinion_descargada_en && (
            <div className="text-muted-foreground">
              Última descarga: {formatoFecha(empresa.opinion_descargada_en)}
            </div>
          )}
          <Button
            size="sm"
            variant="outline"
            disabled={!tieneCiec || corriendo}
            onClick={() => bajar('opinion')}
          >
            <Icon icon="ph:download-simple-light" className="mr-1.5 size-3.5" />
            {empresa.opinion_path ? 'Volver a descargar' : 'Descargar 32-D'}
          </Button>
          {!tieneCiec && (
            <p className="text-muted-foreground">Requiere CIEC registrada.</p>
          )}
        </section>
      </div>

      {job.estado !== 'idle' && (
        <JobProgress
          estado={job.estado}
          log={job.log}
          resultado={job.resultado}
          error={job.error}
        />
      )}

      {job.error && (
        <Alert variant="destructive">
          <AlertDescription>{job.error}</AlertDescription>
        </Alert>
      )}

      <CaptchaModal captcha={job.captcha} onResolver={job.responderCaptcha} />
    </div>
  );
}
