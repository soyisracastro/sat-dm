# api.todoconta.com — API pública y servidor MCP (diseño / terreno listo)

> Estado (2026-07-20): **gateway construido y en producción** en el VPS
> (`deploy/gateway/`) — REST v1 + MCP, CSF/Opinión/CFDIs/procesador+Excel/
> calculadoras/listas negras, vínculos Abacus. Decidida como **prioridad de
> negocio** (por delante de ContPAQi/Odoo): el objetivo es el primer cliente
> pagando/comprometido en semanas — MVP de validación, no roadmap completo.
> Fase 1 (el paso que falta para poder vender): Swagger/OpenAPI y logging de
> uso básico ✅ (2026-07-20); pendiente onboarding asistido de los primeros
> 2-3 clientes con `emitir-key.py` (ya funcional, sin self-serve todavía).
> **OAuth 2.1 para conectores** (claude.ai/ChatGPT) implementado en el gateway
> (2026-07-20, sección "OAuth 2.1" abajo) — pendiente desplegar y probar el
> loop real como conector. Contexto general: [despliegue-web.md](despliegue-web.md).

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

### Vinculación Abacus (WhatsApp)

Abacus (asistente fiscal por WhatsApp, OpenClaw en el mismo VPS) consume la API
pública **por REST v1 con la key de cada suscriptor** — no por MCP, porque un
solo bot atiende N usuarios y la config MCP es estática por workspace.

- **Identidad = número de WhatsApp (E.164)**, igual que la whitelist del
  gatekeeper. El SDK de OpenClaw entrega al plugin `requesterSenderId`
  (runtime-provided, no falsificable por el modelo); el plugin lo resuelve a la
  key del usuario.
- Tabla `asistente_vinculos` (migración `031_asistente_vinculos.sql` en
  todoconta-apps, como la 030 de `api_keys`):
  `whatsapp_e164 (unique) → user_id + api_key_cifrada`. La key viaja cifrada
  con AES-256-GCM (`ASISTENTE_VINCULOS_KEY`, 32 bytes base64, solo en el VPS);
  formato `base64(nonce(12) || ciphertext || tag(16))`. Supabase solo ve el
  blob; `api_keys` sigue guardando únicamente el hash.
- **Emisión + vínculo en un paso**: `emitir-key.py --email … --nombre "Abacus"
  --whatsapp +52…` (scopes sin `mcp`; upsert por número, re-vincular rota la
  key de ese WhatsApp).
- El plugin vive en el repo de Abacus (`plugins/abacus-todoconta/`) y se
  despliega a `~/.openclaw/plugins-local/` en el VPS.
- Self-service (código de verificación desde app.todoconta.com) queda para la
  fase de pricing; hoy la vinculación es manual por script.

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
- **Auth**: dos credenciales conviven — API key en header (Claude Code,
  harnesses, Abacus) y **OAuth 2.1** (conectores de claude.ai/ChatGPT, que NO
  aceptan headers custom). El propio gateway es el authorization server
  (`deploy/gateway/oauth.py`); ver la sección "OAuth 2.1" abajo.
- **Tools** (mismo service layer que REST): `descargar_csf(rfc)`,
  `descargar_opinion(rfc)`, `solicitar_cfdis(rfc, desde, hasta)`,
  `estado_solicitud(id)`, `descargar_zip_cfdis(rfc, id_solicitud)`,
  `excel_cfdis(rfc, desde, hasta, direccion, formato)`,
  `consultar_listas_negras(rfcs[])`, `listar_empresas()`, calculadoras.
- **Archivos: blob embebido, no link** (2026-07-21, corrige el diseño
  original de "links firmados de descarga"). Un QA real mostró el hueco: el
  asistente no tiene la API key del usuario, así que un link por sí solo lo
  dejaba sin poder entregar el archivo en el chat ("Lo ideal sería poder
  llamarlos en el chat"). Ahora `descargar_csf`/`descargar_opinion`/
  `descargar_zip_cfdis`/`excel_cfdis` devuelven el archivo embebido
  (`EmbeddedResource` + `BlobResourceContents` en base64, tipo estándar del
  SDK MCP) en la misma respuesta de la tool — el cliente lo adjunta directo,
  sin una segunda llamada. Tope de 20 MB para ZIP/Excel (un PDF de CSF/Opinión
  nunca se acerca): por encima, cae al link + API key en vez de atorar el
  chat con un blob gigante. La CSF conserva el fallback a la última copia en
  archivo si no hay e.firma o el SAT está caído; la Opinión 32-D NO (es una
  foto de cumplimiento puntual, una vieja engaña). Implementación:
  `deploy/gateway/main.py` (`_mcp_documento`, `_mcp_pdf`, `_mcp_adjuntar`).
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

## Fase 1 (MVP de validación) — estado

- ✅ Migración `api_keys` en todoconta-apps + `emitir-key.py` (alta manual;
  self-serve queda para cuando valide el MVP).
- ✅ Gateway en el VPS (`deploy/gateway/`): REST v1 + MCP + validación de keys
  + rate-limit por key.
- ✅ Logs de uso básicos (2026-07-20): middleware `_log_uso` en `main.py`,
  huella de la key + método + ruta + status + latencia a `docker logs
  gateway`. Insumo para diagnóstico y para facturar después; NO persiste en
  Supabase todavía (deliberado — evitar construir de más antes de validar).
- ✅ OpenAPI/Swagger (2026-07-20): `GET /v1/docs` y `/v1/openapi.json` (antes
  `docs_url=None`). `/internal/vinculos` (Abacus) queda fuera del schema
  (`include_in_schema=False`) — no se documenta ni se vende como parte de v1.
  URL pública canónica: **`https://api.todoconta.com/v1/docs`** (no
  `agente.todoconta.com`) — confirmado que el rewrite `/v1/:path*` del
  proyecto legacy (PR #212, `next.config.ts`) ya cubre `/docs` y
  `/openapi.json` sin cambios; el "Try it out" de Swagger funciona ahí porque
  el OpenAPI generado no fija `servers` (usa el origen de la página).
- ✅ Landing `todoconta.com/api` (2026-07-20, todoconta-apps): página para
  integradores con capacidades, ejemplo `curl`, link a `/v1/docs` y formulario
  "Agenda tu demo" → CRM (`fuente: api-demo`). Sin self-serve de pricing
  (modelo demo-gated ya decidido); el equipo revisa el CRM a mano.
- ⬜ Onboarding manual/asistido de los primeros 2-3 clientes (mismo patrón que
  `emitir-key.py --whatsapp` de Abacus, sin self-serve completo).
- **`/mcp` NO tiene rewrite en `api.todoconta.com`** (solo `/v1/:path*`) — se
  conecta directo a `agente.todoconta.com/mcp` (confirmado con 404 al probar
  vía `api.todoconta.com/mcp`). Correcto tal cual: no es un pendiente, es
  cómo está diseñado hoy (ver plan B `mcp.todoconta.com` en la sección de
  arquitectura arriba, si el streaming por Vercel llega a dar lata).

## OAuth 2.1 — conectores de claude.ai/ChatGPT (2026-07-20)

El paso que abre el MCP a usuarios finales: los conectores de claude.ai
(web/Work) y ChatGPT no aceptan headers custom; exigen el flujo OAuth del
estándar MCP. El gateway es el **authorization server** completo
(`deploy/gateway/oauth.py`), sin dependencias nuevas:

- **Descubrimiento**: `/.well-known/oauth-protected-resource` (RFC 9728) y
  `/.well-known/oauth-authorization-server` (RFC 8414; también responde
  `openid-configuration` y las variantes con sufijo `/mcp` — los conectores
  prueban distintas). El 401 de `/mcp` lleva
  `WWW-Authenticate: Bearer resource_metadata="…"`, que es lo que dispara el
  flujo en el conector.
- **Registro dinámico** (RFC 7591, claude.ai lo exige): `POST /oauth/register`
  → `client_id` público sin secret; redirect_uris solo https (http únicamente
  en localhost, para el MCP Inspector).
- **`GET/POST /oauth/authorize`**: página de login + consentimiento con
  branding TodoConta (correo+contraseña o código OTP, mismas llamadas GoTrue y
  mensajes en español del provisioner) + **validación de licencia** (mismo
  criterio que la versión web: sin plan activo no se abre espacio). PKCE S256
  obligatorio; `state` y `resource` (RFC 8707) soportados; client_id o
  redirect_uri desconocidos cortan con página de error, nunca redirigen.
- **`POST /oauth/token`**: canje del code (one-shot, TTL 5 min; replay revoca
  la familia completa) → access token opaco `mcp_at_…` (1 h) + refresh
  `mcp_rt_…` **rotativo** (90 días; reusar uno rotado también revoca la
  familia). `POST /oauth/revoke` (RFC 7009) para el disconnect del conector.
- **Storage**: SQLite en el volumen `gateway-datos:/data` (tablas
  clients/codes/tokens; solo hashes SHA-256 de codes y tokens, nunca en claro).
  Rate limit por IP en todo `/oauth/*`; los tokens jamás se loguean.
- **Middleware `/mcp`**: acepta `Authorization: Bearer <token OAuth>` ADEMÁS de
  la API key `tc_…` de siempre (las keys no cambian). El token resuelve al
  mismo `ctx_user` con scope `mcp`.
- **Envs opcionales** (defaults iguales al provisioner): `LICENCIA_URL`,
  `EXIGIR_LICENCIA`, `ALLOWLIST_EMAILS`, `TODOCONTA_SUPABASE_ANON_KEY`,
  `OAUTH_DB_PATH`.
- **Traefik**: el router del gateway ahora también publica `/oauth` y
  `/.well-known` (docker-compose.yml).

**Loop de prueba** (tras rebuild del gateway en el VPS): claude.ai → Settings →
Connectors → Add custom connector → `https://agente.todoconta.com/mcp` → debe
disparar el registro dinámico → login TodoConta → consentimiento → tools
visibles en el chat. Después ChatGPT (developer mode). Verificar el refresh
pasada 1 h. Tests locales: `tests/test_gateway_oauth.py`.

## Pricing — referencia de mercado (Syntage, demo privada 2026-07)

Israel solicitó una demo a Syntage (competidor con más músculo, ver plan de decisión) y
compartió su pricing real + material de ventas — **no es público**, tratarlo como
inteligencia competitiva interna, no citarlo/republicarlo hacia afuera.

### Sus tiers (PM/PF 2025, MXN/mes, sin IVA)

| | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|---|---|---|---|
| Suscripción mensual | $7,500 | $15,000 | $21,250 | $27,500 |
| Entidades únicas/mes | 25 | 75 | 125 | 200 |
| Extracciones/mes | 400 | 1,200 | 2,000 | 3,200 |
| Usuarios | Ilimitado | Ilimitado | Ilimitado | Ilimitado |
| Entidad adicional | $450 | $300 | $255 | $206 |
| Extracción adicional | $28 | $18 | $16 | $12 |

"Entidad" = RFC único procesado en el mes; "extracción" = cada jalón de datos (equivalente
a lo que ya mide nuestro `_log_uso` del gateway — mismo concepto, ya tenemos el gancho
técnico para facturar así si se decide ese modelo).

### Qué cubren ellos que nosotros NO (hoy ni en roadmap cercano)

- **RPC/SIGER** (Registro Público de Comercio) + verificación de existencia de la sociedad.
- **RUG** (Registro Único de Garantías — gravámenes).
- **Buró de Crédito**: integración directa con autorización 100% digital, score BC vía API.
  Requiere licenciamiento con el buró — barrera regulatoria alta, no está en nuestro plan.
- **Syndage Score**: score propio de riesgo (664/850 en su reporte ejemplo) que combina
  SAT + Buró + RPC + RUG. Nuestro equivalente parcial futuro es `cfdi-validator` (Capas
  1-4), pero acotado a CFDI — no combina buró/registro público.
- **Estados financieros reconstruidos completos**: balance, estado de resultados, razones
  financieras (liquidez, actividad, rentabilidad, apalancamiento) multi-año. Nuestro
  procesador da IVA/ISR, top contrapartes e integridad — más acotado.
- Concentración/ranking de clientes y proveedores, nómina histórica, monitoreo con
  alertas de eventos, certificación ISO 27001 + ciberseguro.
- Antigüedad de datos desde 2014 (nosotros dependemos de lo que el SAT permite consultar
  por rango de fechas vía WS, sin histórico ilimitado).

### Su vertical real (por su lista de clientes)

Fondeadora, Clara, Kapital Bank, Finsus, FactorExpres, Fairplay, Jeeves, blu, Bancrea,
munbi, Mifel, Daimler, BNP Paribas, solvento, albo, Klar, cumplo, Exitus Capital, hey
banco, engen — **fintechs/neobancos haciendo originación y scoring de crédito**, no ERPs
ni herramientas de compliance en general. Nuestro público objetivo (fintechs, ERPs de
terceros, compliance) es más amplio pero se traslapa parcialmente con este segmento.

### Ancla sugerida para TodoConta (hipótesis, sujeta a validar con el primer cliente)

Nuestro alcance hoy (CSF, 32-D, CFDI masivo, procesador básico+Excel, calculadoras,
listas negras 69/69-B) es un subconjunto real del de Syntage — falta Buró/RPC/RUG/score
propio/estados financieros completos. Cobrar cerca de sus tiers no sería creíble; cobrar
muy por debajo tira la estrategia de "vender caro, demo-gated" ya decidida. Punto de
partida razonable para cotizar (NO público, solo ancla interna):

- Entrada (~20-25 empresas/mes): **$2,000–$3,000 MXN/mes**
- Siguiente escalón (~75 empresas/mes): **$5,000–$6,500 MXN/mes**
- Entidad adicional: **~$120–180 MXN** · Extracción adicional: **~$8–12 MXN**

Esto es ~30-40% del precio de Syntage para un volumen comparable, coherente con que
cubrimos una fracción real de su alcance. Validar con el apetito real del primer
prospecto antes de fijarlo — el objetivo de Fase 1 sigue siendo cerrar ese primer cliente,
no publicar una tabla de precios perfecta.

## Sprint futuro (fase 2+, solo si Fase 1 valida)

Ya NO están aquí (se completaron): self-serve de `api_keys` (`/cuenta/api`,
apps#214), rewrite `/v1/*` del legacy (PR #212), servidor MCP en el gateway y
OAuth 2.1 para conectores (sección arriba).

1. Persistir logs de uso en Supabase (tabla de facturación), Redis+redundancia
   del gateway, status page, Sentry en el gateway.
2. Decidir pricing/cuotas por key (producto).
3. UI de "conexiones autorizadas" en la cuenta (listar/revocar tokens OAuth
   desde app.todoconta.com; hoy la revocación es el disconnect del conector).
