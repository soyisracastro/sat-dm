'use client';

import { useState } from 'react';
import { KeyRound } from 'lucide-react';

import { useServer } from '@/providers/server-provider';
import { Badge } from '@/components/ui/badge';
import { FielUploadDialog } from '@/components/fiel/fiel-upload-dialog';

export function FielStatus() {
  const { fielStatus } = useServer();
  const [dialogOpen, setDialogOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setDialogOpen(true)}
        className="w-full text-left"
      >
        {fielStatus.loaded ? (
          <Badge
            variant="default"
            className="w-full cursor-pointer justify-start gap-2 bg-green-600 px-3 py-1.5 hover:bg-green-700"
          >
            <KeyRound className="size-3.5" />
            <span className="truncate">{fielStatus.rfc}</span>
          </Badge>
        ) : (
          <Badge
            variant="secondary"
            className="w-full cursor-pointer justify-start gap-2 px-3 py-1.5"
          >
            <KeyRound className="size-3.5" />
            <span>Sin e-firma</span>
          </Badge>
        )}
      </button>

      <FielUploadDialog open={dialogOpen} onOpenChange={setDialogOpen} />
    </>
  );
}
