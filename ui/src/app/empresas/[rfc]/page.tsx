// Server component shell de la ruta dinámica `/empresas/[rfc]`.
//
// La app se distribuye como bundle estático (`output: 'export'` en next.config)
// para que Electron la sirva por `file://`. Con `output: 'export'`, las rutas
// dinámicas tienen que precompilar al menos un param en build-time; pero los
// RFCs son específicos del usuario y solo se conocen en runtime.
//
// Solución: declaramos un único placeholder `_` para satisfacer al builder y
// marcamos `dynamicParams: false`. Next emite ese único `out/empresas/_/`. El
// componente cliente (`empresa-detalle.tsx`) lee el RFC real vía
// `useParams()` al navegar — funciona porque dentro de la app siempre se llega
// vía `<Link>` (router de Next, sin reload). El JS bundle es compartido.
//
// Limitación conocida: si el usuario hace reload con una URL dinámica directa
// (poco común en Electron — no hay barra de URL), aparecerá 404. La corrección
// (catch-all route o custom protocol handler) queda para un PR de pulido.

import { EmpresaDetalle } from './empresa-detalle';

export const dynamic = 'force-static';
export const dynamicParams = false;

export function generateStaticParams() {
  return [{ rfc: '_' }];
}

export default function EmpresaDetallePage() {
  return <EmpresaDetalle />;
}
