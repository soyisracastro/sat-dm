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
import { VistaPrevia } from '@/components/organizador/builder-partes';
import {
  EstructuraCustomBuilder,
  VistaPreviaEstructura,
} from '@/components/organizador/estructura-custom-builder';
import {
  NombreArchivo,
  RenombrarBuilder,
} from '@/components/organizador/renombrar-builder';
import { useEmpresas } from '@/hooks/use-empresas';
import {
  ESTRUCTURAS,
  ESTRUCTURA_CUSTOM,
  NIVELES_CUSTOM,
  NIVELES_REQUIEREN_RFC,
  PARTES_NOMBRE,
  PATRON_CUSTOM,
  PATRONES_NOMBRE,
  PREFIJO_TEXTO,
  type SegmentoCatalogo,
} from '@/lib/constants';
import type {
  OrganizadorRequest,
  RenombrarRequest,
  DeduplicarRequest,
} from '@/lib/types';

// Claves de localStorage donde se recuerdan los builders personalizados.
const NIVELES_STORAGE_KEY = 'organizador:estructura-custom';
const NOMBRE_STORAGE_KEY = 'organizador:nombre-custom';

const NIVELES_DEFAULT = ['anio', 'mes', 'flujo'];
const PARTES_DEFAULT = ['fecha', 'rfc_emisor', 'folio_fiscal'];

/** Filtra segmentos guardados, descartando tokens que ya no existan. */
function filtrarSegmentos(
  raw: unknown,
  catalogo: SegmentoCatalogo[],
): string[] | null {
  if (!Array.isArray(raw) || raw.length === 0) return null;
  const validos = raw.filter(
    (n): n is string =>
      typeof n === 'string' &&
      (n.startsWith(PREFIJO_TEXTO)
        ? n.length > PREFIJO_TEXTO.length
        : catalogo.some((t) => !t.custom && t.value === n)),
  );
  return validos.length > 0 ? validos : null;
}

function leerStorage(key: string): Record<string, unknown> | null {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function escribirStorage(key: string, valor: Record<string, unknown>) {
  try {
    window.localStorage.setItem(key, JSON.stringify(valor));
  } catch {
    // localStorage lleno o bloqueado: el builder sigue funcionando en memoria.
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

  // Builders personalizados (estructura de carpetas y nombre de archivo),
  // restaurados de localStorage. Los tokens "rfc" y "flujo" se resuelven
  // contra la empresa activa.
  const [nivelesCustom, setNivelesCustom] = useState<string[]>(NIVELES_DEFAULT);
  const [partesNombre, setPartesNombre] = useState<string[]>(PARTES_DEFAULT);
  const [separadorNombre, setSeparadorNombre] = useState('-');

  const esCustom = orgEstructura === ESTRUCTURA_CUSTOM;
  const requiereRfc =
    esCustom && nivelesCustom.some((n) => NIVELES_REQUIEREN_RFC.includes(n));
  const rfcActiva = empresas.find((e) => e.default)?.rfc ?? '';

  useEffect(() => {
    const niveles = filtrarSegmentos(
      leerStorage(NIVELES_STORAGE_KEY)?.niveles,
      NIVELES_CUSTOM,
    );
    if (niveles) setNivelesCustom(niveles);

    const nombre = leerStorage(NOMBRE_STORAGE_KEY);
    const partes = filtrarSegmentos(nombre?.partes, PARTES_NOMBRE);
    if (partes) setPartesNombre(partes);
    if (typeof nombre?.separador === 'string') setSeparadorNombre(nombre.separador);
  }, []);

  function cambiarNiveles(niveles: string[]) {
    setNivelesCustom(niveles);
    escribirStorage(NIVELES_STORAGE_KEY, { niveles });
  }

  function cambiarPartes(partes: string[]) {
    setPartesNombre(partes);
    escribirStorage(NOMBRE_STORAGE_KEY, { partes, separador: separadorNombre });
  }

  function cambiarSeparador(separador: string) {
    setSeparadorNombre(separador);
    escribirStorage(NOMBRE_STORAGE_KEY, { partes: partesNombre, separador });
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
    if (requiereRfc && !rfcActiva) return;
    onOrganizar({
      origen: orgOrigen,
      destino: orgDestino,
      estructura: esCustom ? nivelesCustom.join('/') : orgEstructura,
      copiar: orgCopiar,
      ...(requiereRfc ? { rfc: rfcActiva } : {}),
    });
  }, [
    orgOrigen,
    orgDestino,
    orgEstructura,
    orgCopiar,
    esCustom,
    nivelesCustom,
    requiereRfc,
    rfcActiva,
    onOrganizar,
  ]);

  const esNombreCustom = renPatron === PATRON_CUSTOM;

  const handleRenombrar = useCallback(() => {
    if (!renDirectorio) return;
    if (esNombreCustom && partesNombre.length === 0) return;
    onRenombrar({
      directorio: renDirectorio,
      patron: renPatron,
      ...(esNombreCustom
        ? { partes: partesNombre, separador: separadorNombre }
        : {}),
    });
  }, [
    renDirectorio,
    renPatron,
    esNombreCustom,
    partesNombre,
    separadorNombre,
    onRenombrar,
  ]);

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

                <div className="pt-1">
                  {esCustom ? (
                    <EstructuraCustomBuilder
                      niveles={nivelesCustom}
                      onChange={cambiarNiveles}
                      rfcEmpresa={rfcActiva || undefined}
                    />
                  ) : (
                    <VistaPreviaEstructura
                      estructura={orgEstructura}
                      rfcEmpresa={rfcActiva || undefined}
                    />
                  )}
                </div>
              </div>

              {requiereRfc && (
                <p className="text-xs text-muted-foreground">
                  {rfcActiva ? (
                    <>
                      Los CFDIs se clasificarán como emitidos o recibidos de la
                      empresa activa:{' '}
                      <span className="font-mono text-foreground">
                        {rfcActiva}
                      </span>
                    </>
                  ) : (
                    'Necesitas una empresa activa para usar RFC de la empresa o Emitidos/Recibidos.'
                  )}
                </p>
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
                  (requiereRfc && !rfcActiva) ||
                  (esCustom && nivelesCustom.length === 0)
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
                    <SelectItem value={PATRON_CUSTOM}>Personalizado…</SelectItem>
                  </SelectContent>
                </Select>

                <div className="pt-1">
                  {esNombreCustom ? (
                    <RenombrarBuilder
                      partes={partesNombre}
                      onChange={cambiarPartes}
                      separador={separadorNombre}
                      onSeparadorChange={cambiarSeparador}
                      rfcEmpresa={rfcActiva || undefined}
                    />
                  ) : (
                    <VistaPrevia>
                      <NombreArchivo
                        nombre={
                          PATRONES_NOMBRE.find((p) => p.value === renPatron)
                            ?.ejemplo(rfcActiva || undefined) ?? ''
                        }
                      />
                    </VistaPrevia>
                  )}
                </div>
              </div>

              <Button
                onClick={handleRenombrar}
                disabled={
                  isLoading ||
                  !renDirectorio ||
                  (esNombreCustom && partesNombre.length === 0)
                }
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
