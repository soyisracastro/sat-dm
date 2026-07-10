// ---------------------------------------------------------------------------
// Feature flags de la app. Un solo punto para prender/apagar features en
// preparación sin borrar su código.
// ---------------------------------------------------------------------------

/**
 * Renovación de e.firma en línea (generar/enviar el .ren, reanudar un envío
 * fallido y descargar el certificado pendiente).
 *
 * DESHABILITADA temporalmente (2026-07-09): el trámite corre el portal del SAT
 * con Playwright desde el agente EMPACADO, y en Windows hay intermitencia de
 * ejecución (además de antivirus que interrumpe sat-agent.exe / TodoConta.exe
 * y entorpece el flujo). La lógica está completa y probada; se reactiva —con
 * cambiar esto a `true`— cuando la ejecución empacada sea estable. Mientras,
 * la UI muestra el botón como «Disponible próximamente».
 *
 * Anotado `: boolean` a propósito: sin la anotación TS lo estrecharía al tipo
 * literal `false` y trataría las ramas habilitadas como código muerto — con
 * `boolean` sigue siendo un flag real que se puede cambiar a `true` sin tocar
 * nada más.
 */
export const RENOVACION_EFIRMA_HABILITADA: boolean = false;
