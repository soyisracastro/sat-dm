'use client';

// Wrapper de compatibilidad: el cuerpo del hook se generalizó a `use-job.ts`
// (los trámites de Certifica usan el mismo plumbing SSE sin captcha y con el
// estado extra `fase`). Los call sites CIEC existentes siguen importando de aquí.

import { useJob } from './use-job';

export type { JobUiEstado, CaptchaState, LogEntry, JobMeta } from './use-job';

export function useCiecJob() {
  return useJob();
}
