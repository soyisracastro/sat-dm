'use client';

import { useCallback, useEffect, useState } from 'react';

import { useServer } from '@/providers/server-provider';
import { Button } from '@/components/ui/button';
import { Icon } from '@/components/ui/icon';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { EstructuraCustomBuilder } from '@/components/organizador/estructura-custom-builder';
import { useEmpresas } from '@/hooks/use-empresas';
import {
  ESTRUCTURAS,
  ESTRUCTURA_CUSTOM,
  NIVELES_CUSTOM,
  NIVELES_REQUIEREN_RFC,
  PATRONES_NOMBRE,
} from '@/lib/constants';
import type {
  OrganizadorRequest,
  RenombrarRequest,
  DeduplicarRequest,
} from '@/lib/types';

/** Clave de localStorage donde se recuerda la última estructura personalizada. */
const NIVELES_STORAGE_KEY = 'organizador:estructura-custom';

const NIVELES_DEFAULT = ['anio', 'mes', 'flujo'];

/** Restaura los niveles guardados, descartando tokens que ya no existan. */
function leerNivelesGuardados(): string[] | null {
  try {
    const raw = window.localStorage.getItem(NIVELES_STORAGE_KEY);
    if (!raw) return null;
    const { niveles } = JSON.parse(raw) as { niveles?: unknown };
    if (!Array.isArray(niveles) || niveles.length === 0) return null;
    const validos = niveles.filter(
      (n): n is string =>
        typeof n === 'string' && NIVELES_CUSTOM.some((t) => t.value === n),
    );
    return validos.length > 0 ? validos : null;
  } catch {
    return null;
  }
}

/** Selector de carpeta nativo del SO (solo en Electron); null en navegador. */
function elegirCarpetaNativo(): Promise<string | null> | null {
  if (typeof window === 'undefined') return null;
  const d = (window as unknown as {
    satDesktop?: { elegirCarpeta?: () => Promise<string | null> };
  }).satDesktop;
  return d?.elegirCarpeta ? d.elegirCarpeta() : null;
}

interface OrganizadorFormProps {
  onOrganizar: (request: OrganizadorRequest) => void;
  onRenombrar: (request: RenombrarRequest) => void;
  onDeduplicar: (request: DeduplicarRequest) => void;
  isLoading: boolean;
}

interface DirectoryFieldProps {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  /** Mostrar botón "Examinar" (solo si hay selector nativo del SO). */
  examinable: boolean;
  placeholder?: string;
}

function DirectoryField({
  id,
  label,
  value,
  onChange,
  examinable,
  placeholder,
}: DirectoryFieldProps) {
  async function examinar() {
    const picker = elegirCarpetaNativo();
    if (!picker) return;
    const elegida = await picker;
    if (elegida) onChange(elegida);
  }

  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <div className="flex gap-2">
        <Input
          id={id}
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="font-mono text-xs"
        />
        {examinable && (
          <Button
            type="button"
            variant="outline"
            onClick={examinar}
            title="Examinar carpeta"
          >
            <Icon icon="ph:folder-open-light" className="size-4" />
            Examinar
          </Button>
        )}
      </div>
    </div>
  );
}

export function OrganizadorForm({
  onOrganizar,
  onRenombrar,
  onDeduplicar,
  isLoading,
}: OrganizadorFormProps) {
  const { apiClient } = useServer();

  const { empresas } = useEmpresas();

  // Organizar
  const [orgOrigen, setOrgOrigen] = useState('');
  const [orgDestino, setOrgDestino] = useState('');
  const [orgEstructura, setOrgEstructura] = useState<string>(ESTRUCTURAS[0].value);
  // Conservar copia del original por default — no perder XMLs por accidente.
  const [orgCopiar, setOrgCopiar] = useState(true);
  // Hasta que el usuario lo edita, destino sigue al origen (caso común: organizar in-place).
  const [destinoTouched, setDestinoTouched] = useState(false);

  // Estructura personalizada: niveles del builder + RFC de la empresa (para
  // los tokens "rfc" y "flujo"). Los niveles se restauran de localStorage.
  const [nivelesCustom, setNivelesCustom] = useState<string[]>(NIVELES_DEFAULT);
  const [orgRfc, setOrgRfc] = useState('');

  const esCustom = orgEstructura === ESTRUCTURA_CUSTOM;
  const requiereRfc =
    esCustom && nivelesCustom.some((n) => NIVELES_REQUIEREN_RFC.includes(n));

  useEffect(() => {
    const guardados = leerNivelesGuardados();
    if (guardados) setNivelesCustom(guardados);
  }, []);

  // Prefila el RFC con la empresa activa; editable y sin pisar lo escrito.
  useEffect(() => {
    const activa = empresas.find((e) => e.default);
    if (activa) setOrgRfc((prev) => prev || activa.rfc);
  }, [empresas]);

  function cambiarNiveles(niveles: string[]) {
    setNivelesCustom(niveles);
    try {
      window.localStorage.setItem(
        NIVELES_STORAGE_KEY,
        JSON.stringify({ niveles }),
      );
    } catch {
      // localStorage lleno o bloqueado: el builder sigue funcionando en memoria.
    }
  }

  // Renombrar
  const [renDirectorio, setRenDirectorio] = useState('');
  const [renPatron, setRenPatron] = useState<string>(PATRONES_NOMBRE[0].value);

  // Deduplicar
  const [dedDirectorio, setDedDirectorio] = useState('');
  const [dedDryRun, setDedDryRun] = useState(true);

  // ¿Hay selector nativo del SO? (Electron sí, navegador no).
  const [examinable, setExaminable] = useState(false);

  useEffect(() => {
    setExaminable(
      typeof window !== 'undefined' &&
        !!(window as unknown as { satDesktop?: unknown }).satDesktop,
    );
  }, []);

  // Prefila los 4 campos de directorio con la carpeta base configurada en Ajustes.
  // Solo si están vacíos, para no pisar lo que el usuario ya escribió.
  useEffect(() => {
    let cancelado = false;
    apiClient
      .getDescargasDir()
      .then((r) => {
        if (cancelado || !r.dir) return;
        setOrgOrigen((prev) => prev || r.dir);
        setOrgDestino((prev) => prev || r.dir);
        setRenDirectorio((prev) => prev || r.dir);
        setDedDirectorio((prev) => prev || r.dir);
      })
      .catch(() => {});
    return () => {
      cancelado = true;
    };
  }, [apiClient]);

  function cambiarOrigen(v: string) {
    setOrgOrigen(v);
    if (!destinoTouched) setOrgDestino(v);
  }

  function cambiarDestino(v: string) {
    setOrgDestino(v);
    setDestinoTouched(true);
  }

  const handleOrganizar = useCallback(() => {
    if (!orgOrigen || !orgDestino) return;
    const rfc = orgRfc.trim().toUpperCase();
    if (requiereRfc && !rfc) return;
    onOrganizar({
      origen: orgOrigen,
      destino: orgDestino,
      estructura: esCustom ? nivelesCustom.join('/') : orgEstructura,
      copiar: orgCopiar,
      ...(requiereRfc ? { rfc } : {}),
    });
  }, [
    orgOrigen,
    orgDestino,
    orgEstructura,
    orgCopiar,
    esCustom,
    nivelesCustom,
    requiereRfc,
    orgRfc,
    onOrganizar,
  ]);

  const handleRenombrar = useCallback(() => {
    if (!renDirectorio) return;
    onRenombrar({
      directorio: renDirectorio,
      patron: renPatron,
    });
  }, [renDirectorio, renPatron, onRenombrar]);

  const handleDeduplicar = useCallback(() => {
    if (!dedDirectorio) return;
    onDeduplicar({
      directorio: dedDirectorio,
      dry_run: dedDryRun,
    });
  }, [dedDirectorio, dedDryRun, onDeduplicar]);

  return (
    <Card>
      <CardContent className="pt-6">
        <Tabs defaultValue="organizar">
          <TabsList className="mb-4">
            <TabsTrigger value="organizar">Organizar</TabsTrigger>
            <TabsTrigger value="renombrar">Renombrar</TabsTrigger>
            <TabsTrigger value="deduplicar">Quitar duplicados</TabsTrigger>
          </TabsList>

          {/* ---- Tab: Organizar ---- */}
          <TabsContent value="organizar">
            <div className="space-y-4">
              <DirectoryField
                id="org-origen"
                label="Carpeta de origen"
                value={orgOrigen}
                onChange={cambiarOrigen}
                examinable={examinable}
                placeholder="/ruta/a/xmls"
              />

              <div className="space-y-2">
                <Label htmlFor="org-estructura">Estructura de carpetas</Label>
                <Select value={orgEstructura} onValueChange={setOrgEstructura}>
                  <SelectTrigger id="org-estructura" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ESTRUCTURAS.map((e) => (
                      <SelectItem key={e.value} value={e.value}>
                        {e.label}
                      </SelectItem>
                    ))}
                    <SelectItem value={ESTRUCTURA_CUSTOM}>
                      Personalizada…
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {esCustom && (
                <EstructuraCustomBuilder
                  niveles={nivelesCustom}
                  onChange={cambiarNiveles}
                />
              )}

              {requiereRfc && (
                <div className="space-y-2">
                  <Label htmlFor="org-rfc">RFC de la empresa</Label>
                  <Input
                    id="org-rfc"
                    placeholder="AAA010101AAA"
                    value={orgRfc}
                    onChange={(e) => setOrgRfc(e.target.value)}
                    className="max-w-64 font-mono text-xs uppercase"
                  />
                  <p className="text-xs text-muted-foreground">
                    Se usa para clasificar cada CFDI como emitido o recibido.
                  </p>
                </div>
              )}

              <DirectoryField
                id="org-destino"
                label="Carpeta de destino"
                value={orgDestino}
                onChange={cambiarDestino}
                examinable={examinable}
                placeholder="/ruta/destino"
              />

              <div className="flex items-center gap-3">
                <Switch
                  id="org-copiar"
                  checked={orgCopiar}
                  onCheckedChange={setOrgCopiar}
                />
                <Label htmlFor="org-copiar">
                  Copiar archivos (en vez de mover)
                </Label>
              </div>

              <Button
                onClick={handleOrganizar}
                disabled={
                  isLoading ||
                  !orgOrigen ||
                  !orgDestino ||
                  (requiereRfc && !orgRfc.trim())
                }
              >
                {isLoading ? 'Procesando...' : 'Organizar'}
              </Button>
            </div>
          </TabsContent>

          {/* ---- Tab: Renombrar ---- */}
          <TabsContent value="renombrar">
            <div className="space-y-4">
              <DirectoryField
                id="ren-directorio"
                label="Carpeta a renombrar"
                value={renDirectorio}
                onChange={setRenDirectorio}
                examinable={examinable}
                placeholder="/ruta/a/xmls"
              />

              <div className="space-y-2">
                <Label htmlFor="ren-patron">Nombre del archivo</Label>
                <Select value={renPatron} onValueChange={setRenPatron}>
                  <SelectTrigger id="ren-patron" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {PATRONES_NOMBRE.map((p) => (
                      <SelectItem key={p.value} value={p.value}>
                        {p.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <Button
                onClick={handleRenombrar}
                disabled={isLoading || !renDirectorio}
              >
                {isLoading ? 'Procesando...' : 'Renombrar'}
              </Button>
            </div>
          </TabsContent>

          {/* ---- Tab: Deduplicar ---- */}
          <TabsContent value="deduplicar">
            <div className="space-y-4">
              <DirectoryField
                id="ded-directorio"
                label="Carpeta a revisar"
                value={dedDirectorio}
                onChange={setDedDirectorio}
                examinable={examinable}
                placeholder="/ruta/a/xmls"
              />

              <div className="flex items-center gap-3">
                <Switch
                  id="ded-dryrun"
                  checked={dedDryRun}
                  onCheckedChange={setDedDryRun}
                />
                <Label htmlFor="ded-dryrun">
                  Solo buscar (no eliminar)
                </Label>
              </div>

              <Button
                onClick={handleDeduplicar}
                disabled={isLoading || !dedDirectorio}
              >
                {isLoading
                  ? 'Procesando...'
                  : dedDryRun
                    ? 'Buscar duplicados'
                    : 'Eliminar duplicados'}
              </Button>
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
