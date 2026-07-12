'use client';

import { useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

import { useServer } from '@/providers/server-provider';
import { esWeb } from '@/lib/modo';
import { BrandMark } from '@/components/layout/brand-mark';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Icon } from '@/components/ui/icon';

// ---------------------------------------------------------------------------
// Conexión manual con el agente (solo versión web).
//
// Puerta de entrada del piloto (antes de que exista el provisioner) y
// herramienta de soporte: se capturan la URL del espacio y el token, se prueba
// /health y se guarda la conexión. Después de conectar, el login normal (o la
// sesión ya persistida en el agente) toman el control.
// ---------------------------------------------------------------------------

export default function ConectarPage() {
  const { conectar, desconectar } = useServer();
  const router = useRouter();

  const [baseUrl, setBaseUrl] = useState('');
  const [token, setToken] = useState('');
  const [probando, setProbando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!esWeb()) {
    return (
      <div className="mx-auto max-w-96 px-6 pt-20 text-center text-sm text-muted-foreground">
        Esta página solo aplica a la versión web.{' '}
        <Link href="/" className="font-medium text-primary hover:underline">
          Volver al inicio
        </Link>
      </div>
    );
  }

  async function probarYConectar(e: FormEvent) {
    e.preventDefault();
    const base = baseUrl.trim().replace(/\/+$/, '');
    const tok = token.trim();
    if (!/^https?:\/\//.test(base)) {
      setError('La URL debe empezar con https:// (o http:// en pruebas locales).');
      return;
    }
    if (!tok) {
      setError('Falta el token de acceso.');
      return;
    }
    setError(null);
    setProbando(true);
    try {
      const res = await fetch(`${base}/health?token=${encodeURIComponent(tok)}`);
      if (res.status === 401) {
        setError('El token no es válido para ese espacio.');
        return;
      }
      if (!res.ok) {
        setError(`El espacio respondió con un error (${res.status}). Verifica la URL.`);
        return;
      }
      conectar({ baseUrl: base, token: tok });
      router.replace('/');
    } catch {
      setError('No se pudo contactar el espacio. Verifica la URL y tu conexión.');
    } finally {
      setProbando(false);
    }
  }

  return (
    <div className="flex min-h-full justify-center bg-background px-6 pb-10 pt-14">
      <div className="w-full max-w-96">
        <div className="mb-6 flex justify-center">
          <BrandMark size={46} wordmarkSize={24} priority iconClassName="rounded-xl shadow-sm" />
        </div>
        <h1 className="mb-2 text-center text-[26px] font-bold leading-[1.22] tracking-[-0.02em] text-foreground">
          Conectar con mi espacio
        </h1>
        <p className="mb-8 text-center text-sm leading-relaxed text-muted-foreground">
          Captura los datos de tu espacio TodoConta en la nube. Normalmente no
          necesitas esta página: el inicio de sesión conecta solo.
        </p>

        <form onSubmit={probarYConectar} noValidate>
          <div className="mb-4.5">
            <label
              htmlFor="conectar-url"
              className="mb-2 block text-[13px] font-semibold text-foreground"
            >
              URL de tu espacio
            </label>
            <Input
              id="conectar-url"
              type="url"
              placeholder="https://agente.todoconta.com/u/…"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              className="font-mono text-xs"
            />
          </div>
          <div className="mb-4.5">
            <label
              htmlFor="conectar-token"
              className="mb-2 block text-[13px] font-semibold text-foreground"
            >
              Token de acceso
            </label>
            <Input
              id="conectar-token"
              type="password"
              placeholder="Token que te compartió soporte"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              className="font-mono text-xs"
            />
          </div>

          {error && (
            <p
              role="alert"
              className="mb-3 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-[13px] leading-snug text-destructive"
            >
              {error}
            </p>
          )}

          <Button type="submit" className="w-full" disabled={probando}>
            {probando ? (
              <Icon icon="ph:circle-notch-light" className="size-4 animate-spin" />
            ) : (
              'Probar y conectar'
            )}
          </Button>
        </form>

        <button
          type="button"
          className="mt-6 block w-full text-center text-[13px] font-medium text-muted-foreground hover:text-foreground"
          onClick={() => {
            desconectar();
            setError(null);
          }}
        >
          Olvidar la conexión guardada en este navegador
        </button>
      </div>
    </div>
  );
}
