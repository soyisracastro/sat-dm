'use client';

import { useCallback, useState } from 'react';

import { Button } from '@/components/ui/button';
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
import { ESTRUCTURAS, PATRONES_NOMBRE } from '@/lib/constants';
import type {
  OrganizadorRequest,
  RenombrarRequest,
  DeduplicarRequest,
} from '@/lib/types';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface OrganizadorFormProps {
  onOrganizar: (request: OrganizadorRequest) => void;
  onRenombrar: (request: RenombrarRequest) => void;
  onDeduplicar: (request: DeduplicarRequest) => void;
  isLoading: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function OrganizadorForm({
  onOrganizar,
  onRenombrar,
  onDeduplicar,
  isLoading,
}: OrganizadorFormProps) {
  // Organizar state
  const [orgOrigen, setOrgOrigen] = useState('');
  const [orgDestino, setOrgDestino] = useState('');
  const [orgEstructura, setOrgEstructura] = useState<string>(ESTRUCTURAS[0].value);
  const [orgCopiar, setOrgCopiar] = useState(false);

  // Renombrar state
  const [renDirectorio, setRenDirectorio] = useState('');
  const [renPatron, setRenPatron] = useState<string>(PATRONES_NOMBRE[0].value);

  // Deduplicar state
  const [dedDirectorio, setDedDirectorio] = useState('');
  const [dedDryRun, setDedDryRun] = useState(true);

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------

  const handleOrganizar = useCallback(() => {
    if (!orgOrigen || !orgDestino) return;
    onOrganizar({
      origen: orgOrigen,
      destino: orgDestino,
      estructura: orgEstructura,
      copiar: orgCopiar,
    });
  }, [orgOrigen, orgDestino, orgEstructura, orgCopiar, onOrganizar]);

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
            <TabsTrigger value="deduplicar">Deduplicar</TabsTrigger>
          </TabsList>

          {/* ---- Tab: Organizar ---- */}
          <TabsContent value="organizar">
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="org-origen">Directorio origen</Label>
                <Input
                  id="org-origen"
                  placeholder="/ruta/a/xmls"
                  value={orgOrigen}
                  onChange={(e) => setOrgOrigen(e.target.value)}
                />
              </div>

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
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="org-destino">Directorio destino</Label>
                <Input
                  id="org-destino"
                  placeholder="/ruta/destino"
                  value={orgDestino}
                  onChange={(e) => setOrgDestino(e.target.value)}
                />
              </div>

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
                disabled={isLoading || !orgOrigen || !orgDestino}
              >
                {isLoading ? 'Procesando...' : 'Organizar'}
              </Button>
            </div>
          </TabsContent>

          {/* ---- Tab: Renombrar ---- */}
          <TabsContent value="renombrar">
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="ren-directorio">Directorio</Label>
                <Input
                  id="ren-directorio"
                  placeholder="/ruta/a/xmls"
                  value={renDirectorio}
                  onChange={(e) => setRenDirectorio(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="ren-patron">Patron de nombre</Label>
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
              <div className="space-y-2">
                <Label htmlFor="ded-directorio">Directorio</Label>
                <Input
                  id="ded-directorio"
                  placeholder="/ruta/a/xmls"
                  value={dedDirectorio}
                  onChange={(e) => setDedDirectorio(e.target.value)}
                />
              </div>

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
