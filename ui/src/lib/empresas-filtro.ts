// ---------------------------------------------------------------------------
// Filtros, orden y "requieren atención" de la lista de Empresas (client-side).
// Funciones puras sobre Empresa[] — la página las compone con su estado local.
// ---------------------------------------------------------------------------

import type { Empresa } from './types';
import { tipoPersona, type TipoPersona } from './empresa-visual';
import { semaforoVencimiento } from './vencimiento';

export type FiltroTipo = 'todas' | TipoPersona;
export type FiltroEstado = 'todos' | 'atencion' | 'aldia';
export type OrdenEmpresas = 'nombre' | 'rfc' | 'vencer' | 'atencion';

export const ORDENES: Record<OrdenEmpresas, string> = {
  nombre: 'Nombre (A–Z)',
  rfc: 'RFC (A–Z)',
  vencer: 'e.firma por vencer',
  atencion: 'Requieren atención',
};

/**
 * Una empresa "requiere atención" si su e.firma está por vencer o vencida
 * (semáforo ámbar/rojo) o si nunca se ha descargado su CSF.
 */
export function requiereAtencion(e: Empresa): boolean {
  if (e.metodos.includes('fiel')) {
    const sem = semaforoVencimiento(e.vencimiento);
    if (sem && sem.estado !== 'verde') return true;
  }
  return !e.csf_path;
}

/** Días hasta el vencimiento para ordenar: sin e.firma → al final. */
function diasParaOrden(e: Empresa): number {
  if (!e.metodos.includes('fiel')) return Number.POSITIVE_INFINITY;
  const sem = semaforoVencimiento(e.vencimiento);
  return sem ? sem.dias : Number.POSITIVE_INFINITY;
}

export function filtrarEmpresas(
  empresas: Empresa[],
  { q, tipo, estado }: { q: string; tipo: FiltroTipo; estado: FiltroEstado },
): Empresa[] {
  const term = q.trim().toLowerCase();
  return empresas.filter((e) => {
    if (tipo !== 'todas' && tipoPersona(e.rfc) !== tipo) return false;
    if (estado === 'atencion' && !requiereAtencion(e)) return false;
    if (estado === 'aldia' && requiereAtencion(e)) return false;
    if (
      term &&
      !e.nombre.toLowerCase().includes(term) &&
      !e.rfc.toLowerCase().includes(term)
    ) {
      return false;
    }
    return true;
  });
}

export function ordenarEmpresas(empresas: Empresa[], orden: OrdenEmpresas): Empresa[] {
  const lista = [...empresas];
  switch (orden) {
    case 'rfc':
      return lista.sort((a, b) => a.rfc.localeCompare(b.rfc));
    case 'vencer':
      return lista.sort((a, b) => diasParaOrden(a) - diasParaOrden(b));
    case 'atencion':
      return lista.sort((a, b) => {
        const delta = Number(requiereAtencion(b)) - Number(requiereAtencion(a));
        return delta !== 0 ? delta : diasParaOrden(a) - diasParaOrden(b);
      });
    case 'nombre':
    default:
      return lista.sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'));
  }
}
