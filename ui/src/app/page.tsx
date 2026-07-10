'use client';

import { useEffect, useMemo, useState } from 'react';

import { DescargasRecientes } from '@/components/inicio/descargas-recientes';
import { EmpresasMovimiento } from '@/components/inicio/empresas-movimiento';
import { EstadoCarteraDonut } from '@/components/inicio/estado-cartera';
import { GraficaCfdisMes } from '@/components/inicio/grafica-cfdis-mes';
import { KpiTile, type KpiTendencia } from '@/components/inicio/kpi-tile';
import { ProximosVencimientos } from '@/components/inicio/proximos-vencimientos';
import { TareasProximamente } from '@/components/inicio/tareas-proximamente';
import { useEmpresas } from '@/hooks/use-empresas';
import { useHistorial } from '@/hooks/use-historial';
import { formatNumber } from '@/lib/formatting';
import {
  cfdisPorMes,
  empresasConMasMovimiento,
  estadoCartera,
  proximosVencimientos,
} from '@/lib/inicio-stats';
import { useAuth } from '@/providers/auth-provider';

/** "Miércoles · 8 de julio de 2026" (capitalizado, con separador del diseño). */
function fechaDeHoy(): string {
  const texto = new Date().toLocaleDateString('es-MX', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
  const [dia, ...resto] = texto.split(', ');
  const capitalizado = dia.charAt(0).toUpperCase() + dia.slice(1);
  return resto.length > 0 ? `${capitalizado} · ${resto.join(', ')}` : capitalizado;
}

/** Primer nombre a partir del email de la cuenta ("israel.castro@…" → "Israel"). */
function primerNombre(email: string | null | undefined): string | null {
  const token = (email ?? '').split('@')[0].split(/[._\-+]/).find(Boolean);
  if (!token) return null;
  return token.charAt(0).toUpperCase() + token.slice(1);
}

export default function InicioPage() {
  const { license } = useAuth();
  const { empresas } = useEmpresas();
  const { descargas, loading: cargandoHistorial } = useHistorial();

  // La fecha se calcula tras montar: bajo `output: export` el HTML se
  // prerenderiza en build y un `new Date()` en el render inicial dejaría la
  // fecha del build (mismatch de hidratación).
  const [hoy, setHoy] = useState('');
  useEffect(() => setHoy(fechaDeHoy()), []);

  const cartera = useMemo(() => estadoCartera(empresas), [empresas]);
  const meses = useMemo(() => cfdisPorMes(descargas), [descargas]);
  const vencimientos = useMemo(() => proximosVencimientos(empresas), [empresas]);
  const movimiento = useMemo(
    () => empresasConMasMovimiento(descargas),
    [descargas],
  );

  const mesActual = meses[meses.length - 1];
  const mesPrevio = meses[meses.length - 2];

  let tendenciaCfdis: KpiTendencia | undefined;
  if (mesActual && mesPrevio && mesPrevio.total > 0) {
    const pct = Math.round(
      ((mesActual.total - mesPrevio.total) / mesPrevio.total) * 100,
    );
    tendenciaCfdis = {
      texto: `${pct >= 0 ? '+' : ''}${pct}% vs. ${mesPrevio.nombre}`,
      tono: pct >= 0 ? 'positiva' : 'neutra',
    };
  }

  const nombre = primerNombre(license?.email);
  const nActivas = cartera.activas.length;

  return (
    <div className="space-y-5">
      {/* Saludo */}
      <div>
        <div className="mb-3 font-mono text-[11.5px] font-semibold uppercase tracking-wide text-muted-foreground/70">
          {hoy || ' '}
        </div>
        <h1 className="text-[27px] font-extrabold leading-tight tracking-tight">
          Hola{nombre ? `, ${nombre}` : ''}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Resumen de tu operación
          {nActivas > 0 &&
            ` · ${nActivas} ${nActivas === 1 ? 'empresa activa' : 'empresas activas'}`}
          .
        </p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-3.5 xl:grid-cols-4">
        <KpiTile
          icono="ph:clipboard-text-light"
          tono="neutro"
          valor="—"
          etiqueta="Tareas abiertas"
          badge="Próximamente"
        />
        <KpiTile
          icono="ph:download-simple-light"
          tono="azul"
          valor={formatNumber(mesActual?.total ?? 0)}
          etiqueta="CFDIs este mes"
          href="/descarga"
          tendencia={tendenciaCfdis}
        />
        <KpiTile
          icono="ph:buildings-light"
          tono="verde"
          valor={formatNumber(nActivas)}
          etiqueta="Empresas activas"
          href="/empresas"
          tendencia={
            nActivas > 0
              ? {
                  texto: `${cartera.alDia} al día`,
                  tono: cartera.alDia > 0 ? 'positiva' : 'neutra',
                  icono: 'ph:check-circle-light',
                }
              : undefined
          }
        />
        <KpiTile
          icono="ph:warning-light"
          tono="ambar"
          valor={formatNumber(cartera.porVencer)}
          etiqueta="e.firmas por vencer"
          href="/empresas"
          valorEnAlerta={cartera.porVencer > 0}
          tendencia={{ texto: '≤ 30 días', tono: 'neutra' }}
        />
      </div>

      {/* Tareas — la sección llega en el siguiente sprint */}
      <TareasProximamente />

      {/* Analítica de operación */}
      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[1.35fr_1fr]">
        <GraficaCfdisMes meses={meses} cargando={cargandoHistorial} />
        <EstadoCarteraDonut cartera={cartera} />
        <ProximosVencimientos items={vencimientos} />
        <EmpresasMovimiento items={movimiento} cargando={cargandoHistorial} />
        <DescargasRecientes
          descargas={descargas.slice(0, 4)}
          cargando={cargandoHistorial}
          className="lg:col-span-2"
        />
      </div>
    </div>
  );
}
