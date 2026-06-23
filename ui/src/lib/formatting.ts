// ---------------------------------------------------------------------------
// Formatting helpers for the SAT Descarga Masiva UI
// ---------------------------------------------------------------------------

const mxnFormatter = new Intl.NumberFormat('es-MX', {
  style: 'currency',
  currency: 'MXN',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const numberFormatter = new Intl.NumberFormat('es-MX');

/**
 * Format a number as Mexican Pesos (MXN) with 2 decimal places.
 *
 * @example formatCurrency(1234.5) // "$1,234.50"
 */
export function formatCurrency(amount: number): string {
  return mxnFormatter.format(amount);
}

/**
 * Format a number with locale-aware thousand separators (es-MX).
 *
 * @example formatNumber(12345) // "12,345"
 */
export function formatNumber(n: number): string {
  return numberFormatter.format(n);
}

/**
 * Format an ISO date string (YYYY-MM-DD or full ISO-8601) to DD/MM/YYYY.
 *
 * Returns the original string when it cannot be parsed.
 *
 * @example formatDate("2025-03-15") // "15/03/2025"
 * @example formatDate("2025-03-15T10:30:00") // "15/03/2025"
 */
export function formatDate(dateStr: string): string {
  if (!dateStr) return '';

  // Handle "YYYY-MM-DD" directly to avoid timezone issues with `new Date()`
  const isoMatch = /^(\d{4})-(\d{2})-(\d{2})/.exec(dateStr);
  if (isoMatch) {
    const [, year, month, day] = isoMatch;
    return `${day}/${month}/${year}`;
  }

  // Fallback: try parsing with Date
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;

  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const year = d.getFullYear();
  return `${day}/${month}/${year}`;
}

/**
 * Format an ISO datetime string to a human-readable date+time in es-MX locale.
 *
 * @example formatDateTime("2025-03-15T10:30:00") // "15/03/2025 10:30"
 */
export function formatDateTime(dateStr: string): string {
  if (!dateStr) return '';

  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;

  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const year = d.getFullYear();
  const hours = String(d.getHours()).padStart(2, '0');
  const minutes = String(d.getMinutes()).padStart(2, '0');

  return `${day}/${month}/${year} ${hours}:${minutes}`;
}

/**
 * Truncate a UUID to its first 8 characters for compact display.
 *
 * @example shortUuid("a1b2c3d4-e5f6-7890-abcd-ef1234567890") // "a1b2c3d4"
 */
export function shortUuid(uuid: string): string {
  return uuid.slice(0, 8);
}

/**
 * Días enteros que faltan hasta una fecha ISO (redondeo hacia arriba, mínimo 0).
 * Devuelve `null` si la fecha es nula o no parseable.
 *
 * @example diasRestantes("2026-07-01T00:00:00Z") // 9
 */
export function diasRestantes(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  if (isNaN(t)) return null;
  const diff = t - Date.now();
  return Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)));
}

/**
 * Pesos enteros sin decimales (para precios de planes).
 *
 * @example formatPesosEnteros(1495) // "$1,495"
 */
export function formatPesosEnteros(amount: number): string {
  return new Intl.NumberFormat('es-MX', {
    style: 'currency',
    currency: 'MXN',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

/**
 * Format a monetary string from the SAT metadata (which may have leading zeros,
 * trailing spaces, or use commas as decimal separators).
 *
 * @example formatMontoSat("1234.56") // "$1,234.56"
 * @example formatMontoSat("") // "$0.00"
 */
export function formatMontoSat(montoStr: string): string {
  if (!montoStr || montoStr.trim() === '') return formatCurrency(0);

  // SAT sometimes uses commas as decimal separator in certain locales
  const cleaned = montoStr.trim().replace(',', '.');
  const n = parseFloat(cleaned);
  if (isNaN(n)) return montoStr;

  return formatCurrency(n);
}
