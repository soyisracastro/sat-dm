"""Borradores de contenido semanal → PR `drafts/semana-NN` en todoconta-apps.

Cada lunes genera con Claude (Sonnet) el paquete de contenido de la semana a
partir de un backlog de temas (dolores reales de clientes + calendario fiscal):

  drafts/semana-NN/post-blog.md      borrador de post (frontmatter del blog listo)
  drafts/semana-NN/guion-video.md    guion de 5-8 min para el video de Israel
  drafts/semana-NN/posts-sociales.md 3 posts (LinkedIn, X/Threads, Facebook)
  drafts/semana-NN/email-sendy.md    1 correo para campaña en Sendy

y abre un PR en el repo de contenido (env CONTENIDO_REPO). NUNCA publica
directo: los archivos viven en drafts/ — mergear el PR tampoco publica nada;
Israel mueve el post a apps/landing/src/content/blog/ cuando lo apruebe.

Uso:
    python agents/contenido_semanal.py            # genera y abre el PR
    python agents/contenido_semanal.py --dry-run  # imprime a stdout, sin PR

Kill switch: OPS_CONTENIDO_ENABLED != "1" → no hace nada (default apagado).
Requiere: ANTHROPIC_API_KEY (la generación ES el agente) y GITHUB_PAT.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lib import github, llm

ESTADO = Path("/data/contenido_estado.json")

REPO_DEFAULT = "soyisracastro/todoconta-apps"

# Backlog editorial: dolores reales (docs/abacus-oportunidades-producto.md) +
# calendario fiscal + pilares del producto. El agente los rota en orden; para
# ajustar la línea editorial basta con editar esta lista y redeployar.
# categorias válidas del blog: comprobantes-fiscales, impuestos-declaraciones,
# cumplimiento-sat, nomina-laboral, regimenes, contabilidad-despachos,
# ia-tecnologia.
TEMAS: list[dict] = [
    {
        "id": "descarga-masiva-3-vias",
        "tema": "Web Service, Contraseña del SAT o e.firma: las 3 vías para descargar tus CFDI y cuándo usar cada una",
        "categorias": ["comprobantes-fiscales"],
        "gancho": "TodoConta Desktop usa las 3 vías y elige la mejor según el volumen; prueba 15 días gratis.",
    },
    {
        "id": "opinion-32d-negativa",
        "tema": "Opinión de cumplimiento 32-D negativa: qué la causa y cómo resolver cada motivo",
        "categorias": ["cumplimiento-sat"],
        "gancho": "TodoConta descarga la 32-D de todas tus empresas y te pinta el semáforo con los motivos.",
    },
    {
        "id": "sbc-imss-parametros",
        "tema": "SBC y cuotas IMSS: los 3 parámetros que cambian el cálculo (días del mes, prima de riesgo, CEyV vigente)",
        "categorias": ["nomina-laboral"],
        "gancho": "Las calculadoras de TodoConta usan tablas oficiales vigentes, no estimaciones.",
    },
    {
        "id": "materialidad-apic",
        "tema": "Materialidad: cómo revisa el SAT que tu operación existió (Activos, Personal, Infraestructura, Capacidad)",
        "categorias": ["cumplimiento-sat"],
        "gancho": "Empieza por tener tus CFDI completos y organizados: descarga masiva con TodoConta.",
    },
    {
        "id": "listas-69-69b",
        "tema": "Listas 69 y 69-B del SAT: qué significan y cómo revisar a tus proveedores antes de deducir",
        "categorias": ["cumplimiento-sat"],
        "gancho": "TodoConta cruza tus CFDI recibidos contra las listas negras del SAT.",
    },
    {
        "id": "diot-2025-layout",
        "tema": "DIOT 2025: cómo armar el archivo de carga masiva de 54 campos sin capturar a mano",
        "categorias": ["impuestos-declaraciones"],
        "gancho": "TodoConta prellena la DIOT desde tus XML y exporta el TXT de carga masiva.",
    },
    {
        "id": "csf-al-dia",
        "tema": "Constancia de Situación Fiscal: por qué te la piden en todos lados y cómo tenerla siempre al día",
        "categorias": ["cumplimiento-sat"],
        "gancho": "TodoConta descarga la CSF de todas tus empresas y extrae regímenes y actividades solos.",
    },
    {
        "id": "errores-portal-sat",
        "tema": "Los errores más comunes del portal del SAT, traducidos: qué significan y qué hacer",
        "categorias": ["cumplimiento-sat"],
        "gancho": "TodoConta reintenta y te avisa cuando el SAT falla — tú no peleas con el portal.",
    },
    {
        "id": "prestamo-socio-dividendo",
        "tema": "Préstamos a socios: cuándo el SAT los recalifica como dividendo ficto y qué documentar",
        "categorias": ["regimenes", "cumplimiento-sat"],
        "gancho": "Ten el expediente de CFDI y estados de cuenta a la mano con TodoConta.",
    },
    {
        "id": "conciliacion-plataformas",
        "tema": "Vendes por plataformas digitales: cómo conciliar lo que te retuvieron contra tus CFDI",
        "categorias": ["impuestos-declaraciones"],
        "gancho": "Descarga todos tus CFDI del periodo y cruza retenciones en el procesador de TodoConta.",
    },
    {
        "id": "papeles-trabajo-xml",
        "tema": "Papeles de trabajo desde tus XML: del ZIP del SAT al Excel que sí usas",
        "categorias": ["contabilidad-despachos"],
        "gancho": "Los procesadores de TodoConta convierten miles de XML en un Excel profesional.",
    },
    {
        "id": "ia-despacho-limites",
        "tema": "IA en el despacho contable: qué sí delegar, qué no, y cómo mantener el control de tu e.firma",
        "categorias": ["ia-tecnologia", "contabilidad-despachos"],
        "gancho": "En TodoConta la IA pide y el software ejecuta — tu e.firma nunca sale de tu equipo.",
    },
    {
        "id": "cierre-mensual-checklist",
        "tema": "Cierre mensual en 90 minutos: el checklist para no empezar de cero cada día 17",
        "categorias": ["contabilidad-despachos", "impuestos-declaraciones"],
        "gancho": "Automatiza la parte 1 del checklist (bajar y validar CFDI) con TodoConta.",
    },
    {
        "id": "efirma-vigilancia",
        "tema": "e.firma vencida: cómo no descubrirlo el día que la necesitas (y qué hacer si ya venció)",
        "categorias": ["cumplimiento-sat"],
        "gancho": "TodoConta te avisa con semáforo cuando la e.firma de cualquier empresa está por vencer.",
    },
]

SISTEMA = (
    "Eres el redactor de contenido de TodoConta (todoconta.com), una app de "
    "escritorio para contadores en México que automatiza la descarga masiva de "
    "CFDI y documentos del SAT (constancia de situación fiscal, opinión 32-D, "
    "DIOT), con procesadores que convierten XML en Excel y calculadoras "
    "fiscales. Precios: prueba gratis 15 días; plan Anual $2,990 MXN; Anual con "
    "IA $4,990 MXN. Escribes en español de México, directo y sin relleno, con "
    "la voz de Israel Castro (contador que construye software): práctico, "
    "honesto, cero humo. Reglas de copy INNEGOCIABLES: di siempre «Contraseña "
    "del SAT (antes CIEC)» en la primera mención y «Contraseña» después, nunca "
    "«CIEC» a secas; nunca uses la palabra «espejo» para la versión web (di "
    "«versión web»); la promesa de privacidad es «tú decides dónde viven tus "
    "datos». No inventes cifras, artículos de ley ni fechas límite: si no estás "
    "seguro de un dato normativo, márcalo como [VERIFICAR]."
)


def _proximo_miercoles(hoy: datetime) -> str:
    dias = (2 - hoy.weekday()) % 7 or 7
    return (hoy + timedelta(days=dias)).strftime("%Y-%m-%d")


def _cargar_estado() -> dict:
    if ESTADO.exists():
        try:
            return json.loads(ESTADO.read_text())
        except Exception:  # noqa: BLE001
            pass
    return {"temas_usados": [], "ultima_semana": None}


def _elegir_tema(estado: dict) -> dict:
    usados = set(estado.get("temas_usados", []))
    pendientes = [t for t in TEMAS if t["id"] not in usados]
    if not pendientes:  # backlog agotado → reinicia el ciclo
        estado["temas_usados"] = []
        pendientes = TEMAS
    return pendientes[0]


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    if os.environ.get("OPS_CONTENIDO_ENABLED", "0") != "1" and not dry_run:
        print("[contenido] apagado por OPS_CONTENIDO_ENABLED — no se hace nada")
        return 0
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[contenido] sin ANTHROPIC_API_KEY — este agente no puede generar")
        return 1
    if not dry_run and not os.environ.get("GITHUB_PAT"):
        print("[contenido] sin GITHUB_PAT — no puedo abrir el PR")
        return 1

    hoy = datetime.now(timezone.utc)
    semana = f"{hoy.isocalendar().year}-{hoy.isocalendar().week:02d}"
    estado = _cargar_estado()
    if estado.get("ultima_semana") == semana and not dry_run:
        print(f"[contenido] la semana {semana} ya se generó — no se repite")
        return 0

    tema = _elegir_tema(estado)
    modelo = os.environ.get("LLM_MODEL_CONTENIDO", "claude-sonnet-5")
    pub_date = _proximo_miercoles(hoy)
    print(f"[contenido] semana {semana} — tema: {tema['id']}")

    post = llm.generar(
        "Escribe un post de blog de 1,000-1,300 palabras sobre este tema:\n"
        f"TEMA: {tema['tema']}\n"
        f"GANCHO DE PRODUCTO (para el bloque cta): {tema['gancho']}\n"
        f"MES ACTUAL: {hoy.strftime('%Y-%m')} (si el calendario fiscal mexicano "
        "tiene una fecha relevante cerca, úsala como percha; si no, no fuerces).\n\n"
        "FORMATO OBLIGATORIO — archivo Markdown que empieza EXACTAMENTE con "
        "frontmatter YAML válido para este schema de Astro:\n"
        "---\n"
        'title: "…" (máx 65 caracteres)\n'
        'description: "…" (140-160 caracteres)\n'
        f"pubDate: {pub_date}\n"
        f"categories: {json.dumps(tema['categorias'])}\n"
        'tags: ["…", "…", "…"] (3-5 tags)\n'
        'heroImage: "/assets/blog/PENDIENTE.jpg"\n'
        "cta:\n"
        '  title: "…"\n'
        '  text: "…" (usa el gancho de producto)\n'
        '  href: "https://todoconta.com/descargar"\n'
        '  cta: "Descargar TodoConta Desktop"\n'
        "---\n\n"
        "Después del frontmatter: el post en Markdown (##/### para secciones, "
        "negritas con moderación, un blockquote con la idea clave). Estructura: "
        "problema concreto → cómo se ve en la práctica → cómo resolverlo paso a "
        "paso → cierre breve. NO menciones TodoConta en el cuerpo más de una "
        "vez; el bloque cta ya vende. Responde SOLO con el archivo, sin "
        "explicaciones alrededor.",
        sistema=SISTEMA,
        modelo=modelo,
        max_tokens=4000,
    )
    if not post:
        print("[contenido] Claude no devolvió el post — abortando")
        return 1

    derivados = llm.generar(
        "A partir de este post de blog, genera las piezas derivadas de la "
        "semana. Responde EXACTAMENTE con tres secciones separadas por líneas "
        "'=== GUION ===', '=== SOCIALES ===' y '=== EMAIL ==='.\n\n"
        "1) GUION: guion de video de 5-8 minutos para YouTube (Israel a "
        "cámara): hook de 15 segundos, desarrollo en 3 bloques con las ideas "
        "del post (indicaciones de pantalla entre corchetes cuando ayude), y "
        "cierre con CTA a descargar TodoConta Desktop. Tono conversacional, "
        "frases cortas para teleprompter.\n"
        "2) SOCIALES: 3 posts listos para pegar — uno para LinkedIn (150-220 "
        "palabras, gancho fuerte en la primera línea, sin hashtags spam, máx "
        "3), uno para X/Threads (hilo corto de 3-4 tuits numerados), uno para "
        "Facebook (100-150 palabras, tono cercano). Cada uno con enlace "
        "https://todoconta.com/blog/ [slug pendiente].\n"
        "3) EMAIL: un correo para la lista de contadores en Sendy: 3 opciones "
        "de asunto (máx 45 caracteres), cuerpo de 150-250 palabras en texto "
        "con UN solo enlace al post, despedida de Israel. Placeholder de "
        "nombre: [Name].\n\n"
        f"POST:\n{post}",
        sistema=SISTEMA,
        modelo=modelo,
        max_tokens=4000,
    )
    if not derivados:
        print("[contenido] Claude no devolvió las piezas derivadas — abortando")
        return 1

    partes: dict[str, str] = {}
    resto = derivados
    for marca, clave in (
        ("=== GUION ===", "guion"),
        ("=== SOCIALES ===", "sociales"),
        ("=== EMAIL ===", "email"),
    ):
        if marca not in resto:
            print(f"[contenido] falta la sección {marca} — abortando")
            return 1
    _, tras_guion = derivados.split("=== GUION ===", 1)
    partes["guion"], tras_sociales = tras_guion.split("=== SOCIALES ===", 1)
    partes["sociales"], partes["email"] = tras_sociales.split("=== EMAIL ===", 1)

    carpeta = f"drafts/semana-{semana}"
    archivos = {
        f"{carpeta}/post-blog.md": post.strip() + "\n",
        f"{carpeta}/guion-video.md": (
            f"# Guion de video — semana {semana}\n\nTema: {tema['tema']}\n\n"
            + partes["guion"].strip()
            + "\n"
        ),
        f"{carpeta}/posts-sociales.md": (
            f"# Posts sociales — semana {semana}\n\n" + partes["sociales"].strip() + "\n"
        ),
        f"{carpeta}/email-sendy.md": (
            f"# Email para Sendy — semana {semana}\n\n" + partes["email"].strip() + "\n"
        ),
    }

    if dry_run:
        for ruta, contenido in archivos.items():
            print(f"\n───── {ruta} ─────\n{contenido}")
        return 0

    url = github.crear_pr_con_archivos(
        repo=os.environ.get("CONTENIDO_REPO", REPO_DEFAULT),
        rama=f"drafts/semana-{semana}",
        titulo=f"drafts: semana {semana} — {tema['tema'][:60]}",
        cuerpo=(
            f"Paquete de contenido de la semana {semana}, generado por el agente "
            "`contenido_semanal` (deploy/ops). **Nada de esto se publica al "
            "mergear** — los archivos viven en `drafts/`.\n\n"
            f"**Tema:** {tema['tema']}\n\n"
            "Checklist de Israel:\n"
            "- [ ] Revisar/editar `post-blog.md` y moverlo a "
            "`apps/landing/src/content/blog/` con su heroImage\n"
            "- [ ] Grabar el video con `guion-video.md` (miércoles)\n"
            "- [ ] Programar `posts-sociales.md`\n"
            "- [ ] Cargar `email-sendy.md` como campaña en Sendy\n\n"
            "Verificar todo dato normativo marcado como [VERIFICAR].\n\n"
            "🤖 Generado por deploy/ops/agents/contenido_semanal.py"
        ),
        archivos=archivos,
    )

    estado.setdefault("temas_usados", []).append(tema["id"])
    estado["ultima_semana"] = semana
    try:
        ESTADO.write_text(json.dumps(estado, ensure_ascii=False))
    except Exception as e:  # noqa: BLE001
        print(f"[contenido] estado no guardado: {e}")

    print(f"[contenido] PR abierto: {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
