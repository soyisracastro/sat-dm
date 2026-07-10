// ---------------------------------------------------------------------------
// Agregaciones del Panel Ejecutivo (Inicio) sobre datos que ya expone el
// agente: catálogo de empresas (GET /empresas) e historial de descargas
// (GET /historial). Funciones puras — la página las memoiza.
//
// Criterio de "CFDIs del mes": mismo que use-status-bar-stats (tipo === 'cfdi'
// con total numérico, agrupado por mes local del timestamp).
// ---------------------------------------------------------------------------

import type { Empresa, HistorialItem } from '@/lib/types';
import {
  semaforoVencimiento,
  type SemaforoVencimiento,
} from '@/lib/vencimiento';

/** Clave local "YYYY-MM" de una fecha. */
function claveMes(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

/** Etiqueta corta del mes en es-MX ("ene", "feb", …) sin el punto final. */
function etiquetaMes(d: Date): string {
  return d.toLocaleDateString('es-MX', { month: 'short' }).replace('.', '');
}

// ---------------------------------------------------------------------------
// CFDIs descargados por mes (gráfica de barras + KPI del mes)
// ---------------------------------------------------------------------------

export interface MesCfdis {
  /** "YYYY-MM" local. */
  clave: string;
  /** "ene", "feb", … */
  etiqueta: string;
  /** Nombre completo del mes ("junio") — para el texto de tendencia. */
  nombre: string;
  total: number;
}

/**
 * Suma de CFDIs descargados por mes (tipo 'cfdi'), últimos `n` meses
 * incluyendo el actual. Los meses sin descargas van con total 0.
 */
export function cfdisPorMes(
  descargas: HistorialItem[],
  n = 6,
  hoy = new Date(),
): MesCfdis[] {
  const totales = new Map<string, number>();
  for (const d of descargas) {
    if (d.tipo !== 'cfdi' || typeof d.total !== 'number') continue;
    const f = new Date(d.timestamp);
    if (Number.isNaN(f.getTime())) continue;
    const clave = claveMes(f);
    totales.set(clave, (totales.get(clave) ?? 0) + d.total);
  }

  const meses: MesCfdis[] = [];
  for (let i = n - 1; i >= 0; i--) {
    const f = new Date(hoy.getFullYear(), hoy.getMonth() - i, 1);
    meses.push({
      clave: claveMes(f),
      etiqueta: etiquetaMes(f),
      nombre: f.toLocaleDateString('es-MX', { month: 'long' }),
      total: totales.get(claveMes(f)) ?? 0,
    });
  }
  return meses;
}

// ---------------------------------------------------------------------------
// Estado de la cartera (donut + KPIs de empresas)
// ---------------------------------------------------------------------------

export interface EstadoCartera {
  /** Empresas no archivadas. */
  activas: Empresa[];
  /** Con e.firma vigente a más de 30 días. */
  alDia: number;
  /** Con e.firma a 30 días o menos de vencer (incluye vencidas). */
  porVencer: number;
  /** Sin e.firma registrada (solo CIEC). */
  soloCiec: number;
}

export function estadoCartera(empresas: Empresa[]): EstadoCartera {
  const activas = empresas.filter((e) => !e.archived_at);
  let alDia = 0;
  let porVencer = 0;
  let soloCiec = 0;
  for (const e of activas) {
    const semaforo = e.metodos.includes('fiel')
      ? semaforoVencimiento(e.vencimiento)
      : null;
    if (!semaforo) soloCiec++;
    else if (semaforo.estado === 'verde') alDia++;
    else porVencer++;
  }
  return { activas, alDia, porVencer, soloCiec };
}

// ---------------------------------------------------------------------------
// Próximos vencimientos de e.firma
// ---------------------------------------------------------------------------

export interface VencimientoEmpresa {
  empresa: Empresa;
  semaforo: SemaforoVencimiento;
}

/**
 * Empresas activas con e.firma en amarillo o rojo (≤ 30 días o vencida),
 * ordenadas de la más urgente a la menos, máximo `max`.
 */
export function proximosVencimientos(
  empresas: Empresa[],
  max = 5,
): VencimientoEmpresa[] {
  const conVencimiento: VencimientoEmpresa[] = [];
  for (const e of empresas) {
    if (e.archived_at || !e.metodos.includes('fiel')) continue;
    const semaforo = semaforoVencimiento(e.vencimiento);
    if (semaforo && semaforo.estado !== 'verde') {
      conVencimiento.push({ empresa: e, semaforo });
    }
  }
  return conVencimiento
    .sort((a, b) => a.semaforo.dias - b.semaforo.dias)
    .slice(0, max);
}

// ---------------------------------------------------------------------------
// Empresas con más movimiento (CFDIs del mes en curso)
// ---------------------------------------------------------------------------

export interface MovimientoEmpresa {
  rfc: string;
  nombre: string;
  total: number;
}

/**
 * Total de CFDIs descargados en el mes en curso por empresa, de mayor a
 * menor, máximo `max`. Solo entradas del historial global (traen `rfc`).
 */
export function empresasConMasMovimiento(
  descargas: HistorialItem[],
  max = 5,
  hoy = new Date(),
): MovimientoEmpresa[] {
  const mesActual = claveMes(hoy);
  const porEmpresa = new Map<string, MovimientoEmpresa>();
  for (const d of descargas) {
    if (d.tipo !== 'cfdi' || typeof d.total !== 'number' || !d.rfc) continue;
    const f = new Date(d.timestamp);
    if (Number.isNaN(f.getTime()) || claveMes(f) !== mesActual) continue;
    const previo = porEmpresa.get(d.rfc);
    if (previo) {
      previo.total += d.total;
    } else {
      porEmpresa.set(d.rfc, {
        rfc: d.rfc,
        nombre: d.nombre || d.rfc,
        total: d.total,
      });
    }
  }
  return [...porEmpresa.values()]
    .sort((a, b) => b.total - a.total)
    .slice(0, max);
}
