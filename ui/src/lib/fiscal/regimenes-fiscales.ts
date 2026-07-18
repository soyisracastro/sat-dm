/**
 * Catálogo de regímenes fiscales SAT (c_RegimenFiscal del Anexo 20 CFDI 4.0).
 * Solo los regímenes vigentes que un contribuyente puede tener configurados.
 */

export interface RegimenFiscalCatalogo {
  clave: string;
  descripcion: string;
  tipoPersona: 'PF' | 'PM' | 'ambos';
}

export const REGIMENES_FISCALES: RegimenFiscalCatalogo[] = [
  // Personas Morales
  { clave: '601', descripcion: 'General de Ley Personas Morales', tipoPersona: 'PM' },
  { clave: '603', descripcion: 'Personas Morales con Fines no Lucrativos', tipoPersona: 'PM' },
  { clave: '620', descripcion: 'Sociedades Cooperativas de Producción', tipoPersona: 'PM' },
  { clave: '622', descripcion: 'Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras', tipoPersona: 'PM' },
  { clave: '623', descripcion: 'Opcional para Grupos de Sociedades', tipoPersona: 'PM' },
  { clave: '624', descripcion: 'Coordinados', tipoPersona: 'PM' },

  // Personas Físicas
  { clave: '605', descripcion: 'Sueldos y Salarios e Ingresos Asimilados a Salarios', tipoPersona: 'PF' },
  { clave: '606', descripcion: 'Arrendamiento', tipoPersona: 'PF' },
  { clave: '607', descripcion: 'Régimen de Enajenación o Adquisición de Bienes', tipoPersona: 'PF' },
  { clave: '608', descripcion: 'Demás Ingresos', tipoPersona: 'PF' },
  { clave: '610', descripcion: 'Residentes en el Extranjero sin Establecimiento Permanente en México', tipoPersona: 'PF' },
  { clave: '611', descripcion: 'Ingresos por Dividendos (socios y accionistas)', tipoPersona: 'PF' },
  { clave: '612', descripcion: 'Personas Físicas con Actividades Empresariales y Profesionales', tipoPersona: 'PF' },
  { clave: '614', descripcion: 'Ingresos por Intereses', tipoPersona: 'PF' },
  { clave: '615', descripcion: 'Régimen de los Ingresos por Obtención de Premios', tipoPersona: 'PF' },
  { clave: '616', descripcion: 'Sin Obligaciones Fiscales', tipoPersona: 'PF' },
  { clave: '621', descripcion: 'Incorporación Fiscal', tipoPersona: 'PF' },
  { clave: '629', descripcion: 'De los Regímenes Fiscales Preferentes y de las Empresas Multinacionales', tipoPersona: 'PF' },

  // Ambos
  { clave: '625', descripcion: 'Régimen de las Actividades Empresariales con Ingresos a través de Plataformas Tecnológicas', tipoPersona: 'ambos' },
  { clave: '626', descripcion: 'Régimen Simplificado de Confianza', tipoPersona: 'ambos' },
];

export function getRegimenesByTipoPersona(
  tipoPersona: 'PF' | 'PM',
): RegimenFiscalCatalogo[] {
  return REGIMENES_FISCALES.filter(
    (r) => r.tipoPersona === tipoPersona || r.tipoPersona === 'ambos',
  );
}

/** Clave del Régimen Simplificado de Confianza (RESICO), PF y PM. */
export const CLAVE_RESICO = '626';

/**
 * Regímenes que por DEFAULT no presentan DIOT (la obligación del art. 32
 * fracc. VIII LIVA sigue al IVA, no al régimen de ISR). Mapeo investigado
 * contra RMF 2025/2026 y RFA 2025 — detalle y fundamentos en
 * docs/producto/diot-2025.md («¿Quién presenta la DIOT?»):
 *
 * - 626 RESICO (PF y PM): relevados por la regla 3.13.19 RMF.
 * - 605, 607, 608, 610, 611, 614, 615, 616, 629: no son sujetos del IVA por
 *   esos ingresos (sueldos, enajenación accidental, dividendos, intereses,
 *   premios, sin obligaciones, REFIPRES).
 * - 621 RIF: relevado si informa proveedores en la bimestral (art. 5-E LIVA
 *   + art. 23 LIF).
 * - 603, 606, 625: condicionales con default NO (no lucrativas sin actos
 *   gravados; arrendamiento — casa habitación exenta y relevación ≤ $4 MDP
 *   de la regla 2.8.1.17 RMF; plataformas con retención definitiva del
 *   art. 18-M LIVA o ≤ $4 MDP).
 *
 * Los que default SÍ: 601, 612 (obligado salvo ingresos ≤ $4 MDP — el
 * usuario lo apaga con el toggle), 620, 622 (facilidad semestral), 623, 624
 * (el coordinado puede presentarla global). El toggle `presenta_diot` de la
 * configuración de la empresa cubre todos los casos condicionales.
 */
const REGIMENES_SIN_DIOT_DEFAULT = new Set([
  '603', '605', '606', '607', '608', '610', '611', '614', '615', '616',
  '621', '625', '626', '629',
]);

/** ¿Este régimen (clave individual) obliga a la DIOT por regla general? */
export function regimenPresentaDiot(clave: string): boolean {
  return !REGIMENES_SIN_DIOT_DEFAULT.has(clave);
}

/**
 * Derivación por régimen: presenta DIOT si ALGÚN régimen configurado la trae
 * por default. Sin regímenes configurados (o clave desconocida) se asume que
 * sí presenta — es el default seguro; omitirla estando obligado genera multas.
 */
export function regimenesPresentanDiot(
  regimenes?: { clave: string }[] | null,
): boolean {
  if (!regimenes || regimenes.length === 0) return true;
  return regimenes.some((r) => regimenPresentaDiot(r.clave));
}

/**
 * ¿La empresa presenta DIOT? El override manual (`presenta_diot`, toggle en la
 * configuración de la empresa) manda; sin override se deriva del régimen.
 */
export function empresaPresentaDiot(
  empresa?: {
    regimenes_fiscales?: { clave: string }[];
    presenta_diot?: boolean | null;
  } | null,
): boolean {
  if (typeof empresa?.presenta_diot === 'boolean') return empresa.presenta_diot;
  return regimenesPresentanDiot(empresa?.regimenes_fiscales);
}
