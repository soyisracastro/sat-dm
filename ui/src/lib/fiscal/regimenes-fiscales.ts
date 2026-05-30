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
