'use client';

// Fallback catastrófico (App Router): solo se activa si el ERROR ocurre en el
// layout raíz o en los providers, donde `error.tsx` ya no puede renderizarse.
// Reemplaza todo el shell, así que debe traer sus propios <html>/<body>. Estilo
// inline (sin Tailwind/componentes) porque no asumimos que el CSS de la app
// haya cargado. Para errores de página normales, ver `error.tsx`.

import { useEffect } from 'react';

import { capturarExcepcion } from '@/lib/telemetria';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('[global-error-boundary]', error);
    capturarExcepcion(error, { boundary: 'global', digest: error?.digest });
  }, [error]);

  return (
    <html lang="es">
      <body
        style={{
          margin: 0,
          fontFamily: 'system-ui, -apple-system, sans-serif',
          background: '#F7F9FC',
          color: '#1f2937',
          display: 'flex',
          minHeight: '100vh',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <div style={{ maxWidth: 420, padding: 24, textAlign: 'center' }}>
          <h1 style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>
            La aplicación tuvo un problema
          </h1>
          <p style={{ fontSize: 14, color: '#6b7280', marginBottom: 16 }}>
            Ocurrió un error inesperado al iniciar la pantalla. Intenta recargar.
          </p>
          <button
            onClick={reset}
            style={{
              padding: '8px 16px',
              fontSize: 14,
              borderRadius: 8,
              border: '1px solid #d1d5db',
              background: '#fff',
              cursor: 'pointer',
            }}
          >
            Reintentar
          </button>
        </div>
      </body>
    </html>
  );
}
