# api.todoconta.com — API pública y servidor MCP (diseño / terreno listo)

> Estado: **diseño aprobado, implementación en sprint futuro.** Este documento
> fija la arquitectura para que ninguna decisión de hoy la estorbe mañana.
> Contexto general: [despliegue-web.md](despliegue-web.md).

## La idea de producto

Dos consumidores nuevos de los servicios que ya tenemos, sin pasar por la UI:

1. **Integradores** (sistemas de terceros): "quiero solo el servicio" — descargar
   documentos del SAT (XML/CFDIs, CSF, Opinión 32-D) desde su propio software,
   autenticados con una API key.
2. **LLMs vía MCP** (Claude web/work/code, y cualquier cliente MCP): el contador
   conecta TodoConta a su asistente y le pide "bájame la constancia de X" o
   "¿algún proveedor mío está en el 69-B?" en lenguaje natural.

## Por qué el terreno YA está casi listo

La versión online resolvió las piezas difíciles:

- **Un agente por usuario en el VPS** con TODA la funcionalidad expuesta por HTTP
  (`/constancia/fiel` y `/opinion/fiel` síncronos; `/solicitar`/`/verificar`/
  `/descargar` para CFDIs; `/descargas/*` sirve los archivos).
- **Derivación determinista** (provisioner): de un `user_id` salen slug, token y
  clave de secretos — cualquier gateway en el VPS puede localizar y encender el
  agente del usuario sin base de datos.
- **`api.todoconta.com`** como cara pública estable (hoy: proyecto legacy en
  Vercel — listas negras, licencias, Stripe).

Lo ÚNICO nuevo que exige la API pública es la **capa de entrada**: API keys y un
gateway que traduzca "key → user_id → su agente".

## Arquitectura objetivo

```
[sistema del cliente / Claude (MCP)]
        │  X-Api-Key: tc_live_…        (REST)
        │  o sesión MCP (Streamable HTTP)
        ▼
https://api.todoconta.com
        ├── /api/*  /auth/*  …        → legacy Next.js (Vercel): listas negras,
        │                               licencias, Stripe (lo de siempre)
        ├── /v1/*                     → rewrite de Vercel → gateway en el VPS
        └── /mcp                      → rewrite de Vercel → gateway en el VPS
                                        (si el streaming por el proxy de Vercel
                                         da lata, plan B: mcp.todoconta.com
                                         directo al VPS vía Traefik, como
                                         agente.todoconta.com)
        ▼
[gateway en el VPS]  (hermano/extensión del provisioner; misma red `agentes`,
        │             misma master key ⇒ deriva slug+token del usuario)
        ▼
[agente-{slug} del usuario]  →  SAT
```

### Autenticación: API keys

- Tabla en Supabase (migración en todoconta-apps): `api_keys`
  (`id, user_id, nombre, key_hash, prefijo, scopes[], creada_en, ultima_vez,
  revocada_en`). Se guarda **solo el hash** (SHA-256); el prefijo (`tc_live_abc…`)
  se muestra para identificarla.
- Emisión/revocación: página "API" en la cuenta del usuario (legacy o espejo) —
  o manual (SQL) para los primeros clientes.
- El gateway valida la key contra Supabase (service role, cache corto), obtiene
  `user_id` y deriva el agente. **Scopes** por key: `documentos:leer`,
  `cfdi:solicitar`, `listas-negras:consultar`, `mcp`.

### Contrato REST v1 (borrador)

| Endpoint | Qué hace | Mapea a (agente) |
|---|---|---|
| `POST /v1/csf` `{rfc}` | PDF de la Constancia | `/constancia/fiel` (síncrono) |
| `POST /v1/opinion` `{rfc}` | PDF de la Opinión 32-D | `/opinion/fiel` (síncrono) |
| `POST /v1/cfdi/solicitudes` `{rfc, desde, hasta, tipo}` | crea solicitud WS | `/solicitar` |
| `GET /v1/cfdi/solicitudes/{id}` | estado (el poller ya trabaja solo) | catálogo de solicitudes |
| `GET /v1/cfdi/solicitudes/{id}/zip` | ZIP de XMLs cuando está lista | `/descargas/zip` |
| `GET /v1/listas-negras/{rfc}` | 69/69-B | legacy (Supabase RPC directo) |

Notas: la empresa (RFC) debe existir en el catálogo del usuario **con
credenciales capturadas** (la e.firma se sube una vez por la UI web — la API no
recibe credenciales de e.firma en v1, decisión de seguridad). Errores del SAT:
mismos contratos que la UI (503 transitorio, etc.).

### Servidor MCP

- **Transporte**: Streamable HTTP (el estándar actual para MCP remoto — es lo
  que consumen Claude web/work/code como "custom connector").
- **Auth**: fase 1 con API key en header (Claude soporta headers custom en
  conectores); fase 2 OAuth 2.1 (el flujo que piden los conectores de claude.ai
  para distribución amplia) — el authorization server puede ser Supabase.
- **Tools** (mismo service layer que REST): `descargar_csf(rfc)`,
  `descargar_opinion(rfc)`, `solicitar_cfdis(rfc, desde, hasta)`,
  `estado_solicitud(id)`, `consultar_listas_negras(rfcs[])`,
  `listar_empresas()`. Los PDFs/ZIPs se devuelven como **links firmados de
  descarga** (no blobs por MCP).
- **Dónde corre**: en el gateway del VPS (Python — FastAPI + SDK MCP oficial),
  junto a la validación de keys y la derivación de agentes. Si el proxy de
  Vercel bufferea el streaming, se publica directo como `mcp.todoconta.com`
  (Traefik ya sabe hacer esto — mismo patrón que agente.todoconta.com).

## Qué se hizo HOY (terreno)

- `api.todoconta.com` agregado al proyecto legacy en Vercel (falta el A record
  `api → 76.76.21.21`, DNS-only, en Cloudflare).
- Los rewrites del espejo y el webhook de Stripe apuntan a `api.todoconta.com`
  (dominio propio: si el legacy se muda de Vercel, solo se repunta el DNS).
- Este documento.

## Sprint futuro (cuando se decida arrancar)

1. Migración `api_keys` en todoconta-apps + página de emisión (o alta manual).
2. Gateway en el VPS (`deploy/gateway/`): REST v1 + validación de keys +
   rate-limit por key + logs de uso (para facturar después).
3. Rewrite `/v1/*` en el proyecto legacy → gateway.
4. Servidor MCP sobre el mismo gateway + probar como conector en Claude.
5. Decidir pricing/cuotas por key (producto).
