'use client';

import { Fragment, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Icon } from '@/components/ui/icon';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type { CfdiListResponse, CfdiRecord } from '@/lib/types';
import { MatchBadge, type EtiquetaLista } from '@/components/listas-negras/match-badge';

interface Props {
  data: CfdiListResponse | null;
  page: number;
  pageSize: number;
  loading: boolean;
  onPage: (p: number) => void;
}

function formatoFecha(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('es-MX', { day: '2-digit', month: 'short', year: 'numeric' });
}

function formatoMXN(n: number): string {
  return new Intl.NumberFormat('es-MX', {
    style: 'currency',
    currency: 'MXN',
    minimumFractionDigits: 2,
  }).format(n);
}

const TIPO_LABEL: Record<string, string> = {
  I: 'Ingreso',
  E: 'Egreso',
  P: 'Pago',
  N: 'Nómina',
  T: 'Traslado',
};

function badgeListaNegra(etiqueta: string | null, rfc: string) {
  if (!etiqueta) {
    return (
      <span className="text-[10px] text-muted-foreground" title={`${rfc} sin validar contra listas negras`}>
        —
      </span>
    );
  }
  // 'EFOS' | 'Aclarado' | '69' | 'Limpio' — MatchBadge ya valida estos valores.
  return <MatchBadge etiqueta={etiqueta as EtiquetaLista} className="text-[10px]" />;
}

function badgeEstado(estado: CfdiRecord['estado_sat']) {
  if (!estado) {
    return (
      <Badge variant="secondary" className="text-[10px]">
        Sin validar
      </Badge>
    );
  }
  if (estado === 'Vigente') {
    return (
      <Badge variant="secondary" className="bg-emerald-100 text-emerald-700 text-[10px]">
        <Icon icon="ph:check-circle-light" className="size-3" /> Vigente
      </Badge>
    );
  }
  if (estado === 'Cancelado') {
    return (
      <Badge variant="destructive" className="text-[10px]">
        <Icon icon="ph:x-circle-light" className="size-3" /> Cancelado
      </Badge>
    );
  }
  return (
    <Badge variant="secondary" className="bg-amber-100 text-amber-700 text-[10px]">
      <Icon icon="ph:warning-light" className="size-3" /> No encontrado
    </Badge>
  );
}

export function CfdiTable({ data, page, pageSize, loading, onPage }: Props) {
  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const [expandido, setExpandido] = useState<string | null>(null);

  if (loading && items.length === 0) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
          <Icon icon="ph:circle-notch-light" className="size-4 animate-spin" />
          Cargando…
        </CardContent>
      </Card>
    );
  }

  if (items.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-2 py-10 text-center">
          <Icon icon="ph:list-magnifying-glass-light" className="size-8 text-muted-foreground" />
          <p className="text-sm font-medium">Sin resultados</p>
          <p className="text-sm text-muted-foreground">
            Ajusta los filtros o carga más XMLs.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden p-0">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-28">Fecha</TableHead>
            <TableHead className="w-24">Tipo</TableHead>
            <TableHead>Emisor</TableHead>
            <TableHead>Receptor</TableHead>
            <TableHead className="text-right">Total</TableHead>
            <TableHead>Estado SAT</TableHead>
            <TableHead>Listas 69/69-B</TableHead>
            <TableHead className="w-10" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((c) => {
            const hayWarnings = (c.warnings?.length ?? 0) > 0;
            const abierto = expandido === c.uuid;
            return (
              <Fragment key={c.uuid}>
                <TableRow
                  className={hayWarnings ? 'bg-amber-50/40' : undefined}
                >
                  <TableCell className="whitespace-nowrap text-sm text-muted-foreground">
                    {formatoFecha(c.fecha)}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="text-[10px]">
                      {TIPO_LABEL[c.tipo] ?? c.tipo}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="font-medium leading-tight">
                      {c.emisor_nombre || '—'}
                    </div>
                    <div className="font-mono text-xs text-muted-foreground">
                      {c.emisor_rfc}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="font-medium leading-tight">
                      {c.receptor_nombre || '—'}
                    </div>
                    <div className="font-mono text-xs text-muted-foreground">
                      {c.receptor_rfc}
                    </div>
                  </TableCell>
                  <TableCell className="text-right font-mono text-sm">
                    {formatoMXN(c.total)}
                    {c.moneda !== 'MXN' && (
                      <div className="text-[10px] text-muted-foreground">{c.moneda}</div>
                    )}
                  </TableCell>
                  <TableCell>{badgeEstado(c.estado_sat)}</TableCell>
                  <TableCell>{badgeListaNegra(c.emisor_en_lista_negra, c.emisor_rfc)}</TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setExpandido(abierto ? null : c.uuid)}
                      title="Ver detalle"
                    >
                      <Icon
                        icon={abierto ? 'ph:caret-up-light' : 'ph:caret-down-light'}
                        className="size-4"
                      />
                    </Button>
                  </TableCell>
                </TableRow>
                {abierto && (
                  <TableRow>
                    <TableCell colSpan={8} className="bg-muted/30">
                      <div className="grid grid-cols-2 gap-4 p-2 text-xs sm:grid-cols-4">
                        <div>
                          <div className="text-muted-foreground">UUID</div>
                          <div className="font-mono">{c.uuid}</div>
                        </div>
                        <div>
                          <div className="text-muted-foreground">Serie / Folio</div>
                          <div className="font-mono">
                            {c.serie || '—'} / {c.folio || '—'}
                          </div>
                        </div>
                        <div>
                          <div className="text-muted-foreground">IVA trasladado</div>
                          <div className="font-mono">{formatoMXN(c.iva_trasladado)}</div>
                        </div>
                        {c.ieps_trasladado > 0 && (
                          <div>
                            <div className="text-muted-foreground">IEPS trasladado</div>
                            <div className="font-mono">{formatoMXN(c.ieps_trasladado)}</div>
                          </div>
                        )}
                        <div>
                          <div className="text-muted-foreground">Retenciones</div>
                          <div className="font-mono">
                            IVA {formatoMXN(c.iva_retenido)} · ISR {formatoMXN(c.isr_retenido)}
                          </div>
                        </div>
                        <div>
                          <div className="text-muted-foreground">Método pago</div>
                          <div>{c.metodo_pago || '—'}</div>
                        </div>
                        <div>
                          <div className="text-muted-foreground">Forma pago</div>
                          <div>{c.forma_pago || '—'}</div>
                        </div>
                        <div>
                          <div className="text-muted-foreground">Uso CFDI</div>
                          <div>{c.receptor_uso_cfdi || '—'}</div>
                        </div>
                        <div>
                          <div className="text-muted-foreground">Lugar expedición</div>
                          <div>{c.lugar_expedicion || '—'}</div>
                        </div>
                      </div>
                      {hayWarnings && (
                        <div className="border-t bg-amber-50/60 p-2 text-xs text-amber-900">
                          <div className="font-medium mb-1">Advertencias</div>
                          <ul className="list-disc pl-4 space-y-0.5">
                            {c.warnings.map((w, i) => (
                              <li key={i}>{w}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                )}
              </Fragment>
            );
          })}
        </TableBody>
      </Table>
      {/* Paginación */}
      <div className="flex items-center justify-between border-t bg-muted/20 px-4 py-2 text-xs text-muted-foreground">
        <div>
          {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} de {total}
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            disabled={page <= 1 || loading}
            onClick={() => onPage(page - 1)}
          >
            <Icon icon="ph:caret-left-light" className="size-3" />
            Anterior
          </Button>
          <span className="px-2 font-mono">
            {page} / {totalPages}
          </span>
          <Button
            variant="ghost"
            size="sm"
            disabled={page >= totalPages || loading}
            onClick={() => onPage(page + 1)}
          >
            Siguiente
            <Icon icon="ph:caret-right-light" className="size-3" />
          </Button>
        </div>
      </div>
    </Card>
  );
}
