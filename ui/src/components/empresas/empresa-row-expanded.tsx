'use client';

import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { useServer } from '@/providers/server-provider';
import { useCiecJob } from '@/hooks/use-ciec-job';
import { Icon } from '@/components/ui/icon';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { CaptchaModal } from '@/components/descarga/captcha-modal';
import { JobProgress } from '@/components/descarga/job-progress';
import { NavegadorStatusBanner } from '@/components/shared/navegador-status';
import { mensajeDeError } from '@/lib/errores';
import { semaforoVencimiento } from '@/lib/vencimiento';
import { metodoPortalPreferido, etiquetaMetodo } from '@/lib/empresa-metodo';
import type { Empresa } from '@/lib/types';

interface Props {
  empresa: Empresa;
  /** Llamado cuando termina un job exitoso, para que el padre refresque el semáforo. */
  onJobDone: () => void;
}

type Documento = 'constancia' | 'opinion';
type ModoAbrir = 'archivo' | 'carpeta';

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
  // Estado FIEL por documento: /constancia/fiel y /opinion/fiel son endpoints
  // distintos y pueden correr en paralelo. Solo CIEC se serializa (el agente
  // rechaza jobs CIEC concurrentes con 409).
  const [fielBusy, setFielBusy] = useState<Record<Documento, boolean>>({
    constancia: false,
    opinion: false,
  });
  const [fielError, setFielError] = useState<string | null>(null);
  // Acción "abrir" (PDF o carpeta) en curso, para deshabilitar el botón mientras
  // el agente local ejecuta el `open`/`explorer`. Solo una a la vez por fila.
  const [accionBusy, setAccionBusy] = useState<{ kind: Documento; modo: ModoAbrir } | null>(null);

  const sem = empresa.vencimiento ? semaforoVencimiento(empresa.vencimiento) : null;
  const tieneFiel = empresa.metodos.includes('fiel');
  const metodo = metodoPortalPreferido(empresa);
  const ciecCorriendo =
    job.estado !== 'idle' &&
    job.estado !== 'done' &&
    job.estado !== 'error' &&
    job.estado !== 'cancelled';

  function botonDisabled(kind: Documento): boolean {
    if (!metodo) return true;
    // Mientras corre un job CIEC, ambos botones se bloquean (limitación backend).
    if (ciecCorriendo) return true;
    // FIEL: solo se bloquea el botón del documento en curso; el otro queda libre.
    return fielBusy[kind];
  }

  useEffect(() => {
    if (job.estado === 'done') onJobDone();
  }, [job.estado, onJobDone]);

  async function bajar(kind: Documento) {
    if (botonDisabled(kind)) return;
    setFielError(null);

    if (metodo === 'fiel') {
      setFielBusy((prev) => ({ ...prev, [kind]: true }));
      try {
        await (kind === 'constancia' ? apiClient.constanciaFiel() : apiClient.opinionFiel());
        toast.success(
          kind === 'constancia' ? 'Constancia descargada' : 'Opinión 32-D descargada',
        );
        onJobDone();
      } catch (e) {
        const msg = mensajeDeError(e);
        setFielError(msg);
        toast.error(msg);
      } finally {
        setFielBusy((prev) => ({ ...prev, [kind]: false }));
      }
      return;
    }

    job.iniciar(
      () =>
        kind === 'constancia'
          ? apiClient.ciecConstancia({ rfc: empresa.rfc })
          : apiClient.ciecOpinion({ rfc: empresa.rfc }),
      { rfc: empresa.rfc },
    );
  }

  async function abrir(kind: Documento, modo: ModoAbrir) {
    const ruta = kind === 'constancia' ? empresa.csf_path : empresa.opinion_path;
    if (!ruta || accionBusy) return;
    setFielError(null);
    setAccionBusy({ kind, modo });
    try {
      await apiClient.abrir(ruta, modo);
    } catch (e) {
      const msg = mensajeDeError(e);
      setFielError(msg);
      toast.error(msg);
    } finally {
      setAccionBusy(null);
    }
  }

  function renderAccionesArchivo(kind: Documento, ruta: string | null | undefined) {
    if (!ruta) return null;
    const ocupado = accionBusy !== null;
    const esPdf = ruta.toLowerCase().endsWith('.pdf');
    const cargandoArchivo = accionBusy?.kind === kind && accionBusy.modo === 'archivo';
    const cargandoCarpeta = accionBusy?.kind === kind && accionBusy.modo === 'carpeta';
    return (
      <>
        {esPdf && (
          <Button
            variant="ghost"
            size="icon"
            onClick={() => abrir(kind, 'archivo')}
            disabled={ocupado}
            title="Abrir el PDF"
          >
            <Icon
              icon={cargandoArchivo ? 'ph:circle-notch-light' : 'ph:file-pdf-light'}
              className={cargandoArchivo ? 'size-4 animate-spin' : 'size-4'}
            />
          </Button>
        )}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => abrir(kind, 'carpeta')}
          disabled={ocupado}
          title="Abrir la carpeta donde se guardó"
        >
          <Icon
            icon={cargandoCarpeta ? 'ph:circle-notch-light' : 'ph:folder-open-light'}
            className={cargandoCarpeta ? 'size-4 animate-spin' : 'size-4'}
          />
        </Button>
      </>
    );
  }

  function renderChip() {
    if (!metodo) return null;
    return (
      <div className="flex items-center gap-1 text-[10px] uppercase tracking-wide text-muted-foreground">
        <Icon
          icon={metodo === 'fiel' ? 'ph:shield-check-light' : 'ph:key-light'}
          className="size-3"
        />
        Usando: {etiquetaMetodo(metodo)}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <NavegadorStatusBanner />

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
          {renderChip()}
          {empresa.csf_descargada_en && (
            <div className="text-muted-foreground">
              Última descarga: {formatoFecha(empresa.csf_descargada_en)}
            </div>
          )}
          <div className="flex items-center gap-1">
            <Button
              size="sm"
              variant="outline"
              disabled={botonDisabled('constancia')}
              onClick={() => bajar('constancia')}
              title={!metodo ? 'Agrega FIEL o CIEC en Empresas' : undefined}
            >
              <Icon icon="ph:download-simple-light" className="mr-1.5 size-3.5" />
              {empresa.csf_path ? 'Volver a descargar' : 'Descargar CSF'}
            </Button>
            {renderAccionesArchivo('constancia', empresa.csf_path)}
          </div>
          {!metodo && (
            <p className="text-muted-foreground">Agrega FIEL o CIEC en Empresas.</p>
          )}
        </section>

        {/* Opinión de Cumplimiento 32-D */}
        <section className="space-y-2 text-xs">
          <div className="flex items-center gap-1.5 font-medium text-foreground">
            <Icon icon="ph:clipboard-text-light" className="size-3.5" />
            Opinión de Cumplimiento 32-D
          </div>
          {renderChip()}
          {empresa.opinion_descargada_en && (
            <div className="text-muted-foreground">
              Última descarga: {formatoFecha(empresa.opinion_descargada_en)}
            </div>
          )}
          <div className="flex items-center gap-1">
            <Button
              size="sm"
              variant="outline"
              disabled={botonDisabled('opinion')}
              onClick={() => bajar('opinion')}
              title={!metodo ? 'Agrega FIEL o CIEC en Empresas' : undefined}
            >
              <Icon icon="ph:download-simple-light" className="mr-1.5 size-3.5" />
              {empresa.opinion_path ? 'Volver a descargar' : 'Descargar 32-D'}
            </Button>
            {renderAccionesArchivo('opinion', empresa.opinion_path)}
          </div>
          {!metodo && (
            <p className="text-muted-foreground">Agrega FIEL o CIEC en Empresas.</p>
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

      {fielError && (
        <Alert variant="destructive">
          <AlertDescription>{fielError}</AlertDescription>
        </Alert>
      )}

      <CaptchaModal captcha={job.captcha} onResolver={job.responderCaptcha} />
    </div>
  );
}
