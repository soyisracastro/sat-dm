// Ruta ESTÁTICA `/empresas/detalle` — detalle/configuración de una empresa.
//
// El RFC viaja como query param (`?rfc=...`), NO como segmento de ruta. Bajo
// `output: 'export'` un segmento dinámico `[rfc]` exige pre-generar cada valor
// en build-time (`generateStaticParams`); como los RFCs solo se conocen en
// runtime, esa ruta caía en 404 → fallback SPA → dashboard. Una ruta estática
// con query param siempre tiene su `index.html`, así que funciona igual en
// navegación SPA y en reload. Ver la convención en ui/CLAUDE.md.
//
// `useSearchParams` (lo usa el cliente) requiere un <Suspense> envolvente bajo
// export estático — lo proveemos aquí.

import { Suspense } from 'react';

import { EmpresaDetalle } from './empresa-detalle';

export default function EmpresaDetallePage() {
  return (
    <Suspense fallback={null}>
      <EmpresaDetalle />
    </Suspense>
  );
}
