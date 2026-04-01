'use client';

import { useCallback, useRef, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent } from '@/components/ui/card';
import type { CfdiValidarInput } from '@/lib/types';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ValidacionInputProps {
  onValidar: (cfdis: CfdiValidarInput[]) => void;
  isValidating: boolean;
}

// ---------------------------------------------------------------------------
// XML parsing helper (browser DOMParser)
// ---------------------------------------------------------------------------

function parseCfdiFromXml(xmlText: string): CfdiValidarInput | null {
  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(xmlText, 'text/xml');

    // Check for parse errors
    const parseError = doc.querySelector('parsererror');
    if (parseError) return null;

    // Try CFDI 3.3 / 4.0 namespace
    const comprobante =
      doc.getElementsByTagNameNS('http://www.sat.gob.mx/cfd/4', 'Comprobante')[0] ??
      doc.getElementsByTagNameNS('http://www.sat.gob.mx/cfd/3', 'Comprobante')[0] ??
      doc.querySelector('Comprobante');

    if (!comprobante) return null;

    const total = parseFloat(comprobante.getAttribute('Total') ?? '0');

    // Emisor
    const emisor =
      doc.getElementsByTagNameNS('http://www.sat.gob.mx/cfd/4', 'Emisor')[0] ??
      doc.getElementsByTagNameNS('http://www.sat.gob.mx/cfd/3', 'Emisor')[0] ??
      doc.querySelector('Emisor');

    const emisorRfc = emisor?.getAttribute('Rfc') ?? '';

    // Receptor
    const receptor =
      doc.getElementsByTagNameNS('http://www.sat.gob.mx/cfd/4', 'Receptor')[0] ??
      doc.getElementsByTagNameNS('http://www.sat.gob.mx/cfd/3', 'Receptor')[0] ??
      doc.querySelector('Receptor');

    const receptorRfc = receptor?.getAttribute('Rfc') ?? '';

    // UUID from TimbreFiscalDigital
    const timbre =
      doc.getElementsByTagNameNS(
        'http://www.sat.gob.mx/TimbreFiscalDigital',
        'TimbreFiscalDigital',
      )[0] ?? doc.querySelector('TimbreFiscalDigital');

    const uuid = timbre?.getAttribute('UUID') ?? '';

    if (!uuid) return null;

    return {
      uuid: uuid.toUpperCase(),
      emisor_rfc: emisorRfc,
      receptor_rfc: receptorRfc,
      total,
    };
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Text parsing helper (CSV/TSV lines)
// ---------------------------------------------------------------------------

function parseCfdisFromText(text: string): CfdiValidarInput[] {
  const lines = text
    .split('\n')
    .map((l) => l.trim())
    .filter((l) => l.length > 0);

  const results: CfdiValidarInput[] = [];

  for (const line of lines) {
    // Split by comma or tab
    const parts = line.split(/[,\t]/).map((p) => p.trim());
    if (parts.length < 1) continue;

    const uuid = parts[0].toUpperCase();
    // Validate UUID format (loose: 36 chars with hyphens)
    if (!/^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$/i.test(uuid)) {
      continue;
    }

    results.push({
      uuid,
      emisor_rfc: parts[1] ?? '',
      receptor_rfc: parts[2] ?? '',
      total: parseFloat(parts[3] ?? '0') || 0,
    });
  }

  return results;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ValidacionInput({ onValidar, isValidating }: ValidacionInputProps) {
  const [xmlCfdis, setXmlCfdis] = useState<CfdiValidarInput[]>([]);
  const [textCfdis, setTextCfdis] = useState<CfdiValidarInput[]>([]);
  const [textValue, setTextValue] = useState('');
  const [activeTab, setActiveTab] = useState('xml');
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // -------------------------------------------------------------------------
  // XML file handling
  // -------------------------------------------------------------------------

  const processFiles = useCallback(async (files: FileList | File[]) => {
    const fileArray = Array.from(files).filter(
      (f) => f.name.toLowerCase().endsWith('.xml'),
    );

    const parsed: CfdiValidarInput[] = [];

    for (const file of fileArray) {
      const text = await file.text();
      const cfdi = parseCfdiFromXml(text);
      if (cfdi) {
        parsed.push(cfdi);
      }
    }

    setXmlCfdis((prev) => {
      // Deduplicate by UUID
      const existing = new Set(prev.map((c) => c.uuid));
      const newOnes = parsed.filter((c) => !existing.has(c.uuid));
      return [...prev, ...newOnes];
    });
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      if (e.dataTransfer.files.length > 0) {
        processFiles(e.dataTransfer.files);
      }
    },
    [processFiles],
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) {
        processFiles(e.target.files);
      }
    },
    [processFiles],
  );

  // -------------------------------------------------------------------------
  // Text parsing
  // -------------------------------------------------------------------------

  const handleParseText = useCallback(() => {
    const parsed = parseCfdisFromText(textValue);
    setTextCfdis(parsed);
  }, [textValue]);

  // -------------------------------------------------------------------------
  // Submit
  // -------------------------------------------------------------------------

  const currentCfdis = activeTab === 'xml' ? xmlCfdis : textCfdis;

  const handleValidar = useCallback(() => {
    if (currentCfdis.length > 0) {
      onValidar(currentCfdis);
    }
  }, [currentCfdis, onValidar]);

  return (
    <Card>
      <CardContent className="pt-6">
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="mb-4">
            <TabsTrigger value="xml">Archivos XML</TabsTrigger>
            <TabsTrigger value="text">Lista de UUIDs</TabsTrigger>
          </TabsList>

          {/* ---- Tab: XML files ---- */}
          <TabsContent value="xml">
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`
                flex min-h-[160px] cursor-pointer flex-col items-center justify-center
                rounded-lg border-2 border-dashed p-6 text-center transition-colors
                ${
                  isDragOver
                    ? 'border-primary bg-primary/5'
                    : 'border-muted-foreground/25 hover:border-muted-foreground/50'
                }
              `}
            >
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".xml"
                onChange={handleFileSelect}
                className="hidden"
              />
              <p className="text-sm font-medium">
                Arrastra archivos XML aqui o haz clic para seleccionar
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                Se extraera UUID, RFC Emisor, RFC Receptor y Total de cada CFDI
              </p>
            </div>

            {xmlCfdis.length > 0 && (
              <div className="mt-3 flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  {xmlCfdis.length} CFDI{xmlCfdis.length !== 1 ? 's' : ''} cargado
                  {xmlCfdis.length !== 1 ? 's' : ''}
                </p>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    setXmlCfdis([]);
                  }}
                >
                  Limpiar
                </Button>
              </div>
            )}
          </TabsContent>

          {/* ---- Tab: UUID list ---- */}
          <TabsContent value="text">
            <div className="space-y-3">
              <textarea
                value={textValue}
                onChange={(e) => setTextValue(e.target.value)}
                placeholder={
                  'UUID, RFC Emisor, RFC Receptor, Total\n' +
                  'ej: A1B2C3D4-E5F6-7890-ABCD-EF1234567890, AAA010101AAA, BBB020202BBB, 1500.00'
                }
                rows={8}
                className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 dark:bg-input/30"
              />
              <div className="flex items-center justify-between">
                <p className="text-xs text-muted-foreground">
                  Una linea por CFDI. Separar campos con coma o tabulador.
                </p>
                <Button variant="outline" size="sm" onClick={handleParseText}>
                  Parsear
                </Button>
              </div>
              {textCfdis.length > 0 && (
                <p className="text-sm text-muted-foreground">
                  {textCfdis.length} CFDI{textCfdis.length !== 1 ? 's' : ''} detectado
                  {textCfdis.length !== 1 ? 's' : ''}
                </p>
              )}
            </div>
          </TabsContent>
        </Tabs>

        {/* ---- Validar button ---- */}
        <div className="mt-6">
          <Button
            onClick={handleValidar}
            disabled={isValidating || currentCfdis.length === 0}
            className="w-full sm:w-auto"
          >
            {isValidating ? 'Validando...' : `Validar ${currentCfdis.length} CFDI${currentCfdis.length !== 1 ? 's' : ''}`}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
