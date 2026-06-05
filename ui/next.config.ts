import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // En producción la app se distribuye como bundle estático servido por Electron
  // desde `file://`. `output: 'export'` produce `ui/out/` con HTML/CSS/JS planos.
  // En dev (`pnpm dev`) Next sigue corriendo en localhost:3001 normalmente —
  // esta opción solo afecta `pnpm build`.
  output: 'export',

  // CRÍTICO para Electron empacado: por default Next.js emite paths absolutos
  // como `/_next/static/chunks/abc.js`. Cuando el bundle se sirve desde
  // `file://...resources/ui/index.html`, el browser resuelve esa raíz como
  // `file:///C:/_next/...` (raíz del disco) y cada chunk falla con
  // ERR_FILE_NOT_FOUND. React nunca arranca → app se queda en el HTML
  // pre-renderizado del SSG (splash "Cargando…") sin posibilidad de hidratar.
  //
  // `assetPrefix: './'` hace que los paths emitidos sean relativos al archivo
  // que los pide, así `index.html` resuelve `./_next/static/...` desde su
  // propia carpeta. Solo en producción — en dev rompe el HMR de Next.
  assetPrefix: process.env.NODE_ENV === 'production' ? './' : undefined,

  // `next/image` requiere optimizar en runtime con un Node server. Bajo `export`
  // no hay server, así que desactivamos la optimización (las imágenes se sirven
  // tal cual desde el bundle).
  images: { unoptimized: true },

  // Variable hardcodeada en el bundle estático. El agente Python corre en un
  // puerto efímero distinto cada arranque; el renderer prefiere
  // `window.satAgent.baseUrl` (inyectado por el preload de Electron) sobre
  // esta env var. Aquí queda como fallback para dev fuera de Electron.
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8787',
  },
};

export default nextConfig;
