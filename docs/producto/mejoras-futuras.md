# Mejoras futuras

Ideas que NO entran en el MVP (prioridad: dejar la app funcional para difusión), pero
que valen la pena en siguientes actualizaciones.

## Historial → enviar documento por correo (AWS SES)

**Idea:** desde el Historial, además de "Ver PDF" / "Abrir carpeta", permitir
**enviar el documento por email** (constancia, opinión 32-D, y a futuro un ZIP de CFDIs).

**UX propuesta:** el usuario solo escribe el correo destino; el envío sale desde
nuestra infraestructura (AWS SES) con **branding de TodoConta** (plantilla HTML,
remitente verificado, asunto claro). Nada de configurar SMTP del usuario.

**Por qué se difiere:** requiere trabajo de backend e infra que no es necesario para
lanzar:
- Credenciales de AWS SES (dominio/remitente verificado, salida de sandbox de SES).
- Las credenciales **no** deben vivir en el agente local (es del usuario final). El
  envío debería ir por un **servicio en la nube** (p. ej. app.todoconta.com) que
  reciba el archivo o un identificador y dispare el correo — el agente local solo
  subiría/referenciaría el documento. Definir ese contrato.
- Plantilla de correo con branding + adjuntar PDF (o link de descarga temporal).
- Límite de tamaño (los ZIP de CFDIs grandes no caben como adjunto → link firmado S3).
- Rate limiting / anti-abuso (es un endpoint que manda correo a terceros).

**Esbozo técnico:** `POST /enviar-documento {ruta, email}` en el agente → sube el
archivo al servicio nube → el servicio manda el correo vía SES. Validar `ruta` contra
el historial (igual que `/abrir`).

Relacionado: integración con app.todoconta.com como servicio en la nube.
