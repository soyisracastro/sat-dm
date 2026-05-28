'use client';

import { useEffect, useState } from 'react';
import { Toaster } from 'sonner';
import { useTheme } from 'next-themes';

/**
 * Monta el contenedor global de toasts (sonner). Coordina el tema visual
 * con next-themes para que claros/oscuros del toast hagan match con la app.
 * Patrón `mounted` evita mismatch de hidratación entre SSR y cliente.
 */
export function SonnerProvider() {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <Toaster
      theme={mounted ? ((resolvedTheme === 'dark' ? 'dark' : 'light') as 'light' | 'dark') : 'system'}
      position="top-right"
      richColors
      closeButton
    />
  );
}
