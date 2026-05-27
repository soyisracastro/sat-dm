// ---------------------------------------------------------------------------
// Semáforo de vencimiento de la e.firma (mismo criterio que TodoConta Apps):
//   🟢 verde     → faltan MÁS de 30 días
//   🟡 amarillo  → faltan 30 días o menos
//   🔴 rojo      → faltan 5 días o menos, o ya venció
// ---------------------------------------------------------------------------

export type EstadoVencimiento = 'verde' | 'amarillo' | 'rojo';

export interface SemaforoVencimiento {
  estado: EstadoVencimiento;
  /** Días hasta el vencimiento (negativo si ya venció, 0 si vence hoy). */
  dias: number;
  /** True si la e.firma ya venció. */
  vencida: boolean;
  /** Fecha de vencimiento normalizada "YYYY-MM-DD". */
  fecha: string;
  /** Texto corto listo para mostrar: "Vence en 12 días", "Vencida hace 3 días", "Vence hoy". */
  label: string;
}

/** Días enteros entre hoy (medianoche local) y la fecha "YYYY-MM-DD". */
function diasHasta(fecha: string): number {
  const [y, m, d] = fecha.split('-').map(Number);
  if (!y || !m || !d) return NaN;
  const objetivo = new Date(y, m - 1, d);
  const hoy = new Date();
  hoy.setHours(0, 0, 0, 0);
  objetivo.setHours(0, 0, 0, 0);
  return Math.round((objetivo.getTime() - hoy.getTime()) / 86_400_000);
}

/**
 * Calcula el semáforo de vencimiento. Devuelve `null` si `vencimiento` está vacío
 * o no tiene formato "YYYY-MM-DD" (p. ej. una empresa solo-CIEC sin e.firma).
 */
export function semaforoVencimiento(
  vencimiento: string | null | undefined,
): SemaforoVencimiento | null {
  if (!vencimiento) return null;
  const dias = diasHasta(vencimiento);
  if (Number.isNaN(dias)) return null;

  const vencida = dias < 0;
  const estado: EstadoVencimiento =
    dias <= 5 ? 'rojo' : dias <= 30 ? 'amarillo' : 'verde';

  let label: string;
  if (vencida) {
    const d = Math.abs(dias);
    label = d === 1 ? 'Vencida hace 1 día' : `Vencida hace ${d} días`;
  } else if (dias === 0) {
    label = 'Vence hoy';
  } else {
    label = dias === 1 ? 'Vence mañana' : `Vence en ${dias} días`;
  }

  return { estado, dias, vencida, fecha: vencimiento, label };
}
