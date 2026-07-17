"""Borradores de contenido semanal → PR `drafts/semana-NN` en todoconta-apps.

Cada lunes genera con Claude (Sonnet) el paquete de contenido de la semana:

  drafts/semana-NN/post-blog.md      borrador de post (frontmatter del blog listo)
  drafts/semana-NN/guion-video.md    guion de 5-8 min para el video de Israel
  drafts/semana-NN/posts-sociales.md 3 posts (LinkedIn, X/Threads, Facebook)
  drafts/semana-NN/email-sendy.md    1 correo para campaña en Sendy

La FUENTE PRIMARIA de temas es el calendario editorial del repo
(apps/landing/editorial/calendario-editorial-2026.csv, leído en runtime vía la
GitHub API): toma la fila más próxima con publicado=no. Israel edita el CSV (o
marca publicado=si) SIN redeployar el contenedor. Si el calendario no está
disponible o se agotó, cae a un backlog embebido (dolores reales de Abacus que
el calendario aún no cubre).

Abre un PR en el repo de contenido (env CONTENIDO_REPO). NUNCA publica
directo: los archivos viven en drafts/ — mergear el PR tampoco publica nada;
Israel mueve el post a apps/landing/src/content/blog/ cuando lo apruebe.

Uso:
    python agents/contenido_semanal.py            # genera y abre el PR
    python agents/contenido_semanal.py --dry-run  # imprime a stdout, sin PR

Kill switch: OPS_CONTENIDO_ENABLED != "1" → no hace nada (default apagado).
Requiere: ANTHROPIC_API_KEY (la generación ES el agente) y GITHUB_PAT.
"""

from __future__ import annotations

import csv
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lib import github, llm

ESTADO = Path("/data/contenido_estado.json")

REPO_DEFAULT = "soyisracastro/todoconta-apps"
CALENDARIO_RUTA_DEFAULT = "apps/landing/editorial/calendario-editorial-2026.csv"

CATEGORIAS_VALIDAS = {
    "comprobantes-fiscales",
    "impuestos-declaraciones",
    "cumplimiento-sat",
    "nomina-laboral",
    "regimenes",
    "contabilidad-despachos",
    "ia-tecnologia",
}

# Backlog de RESPALDO (dolores reales de docs/abacus-oportunidades-producto.md
# que el calendario editorial aún no cubre). Solo se usa si el CSV del repo no
# está disponible o se agotó — la fuente primaria es el calendario. Depurado
# contra lo ya publicado en el blog (SBC, 69-B, DIOT, descarga masiva, IA en
# el despacho y e.firma ya tienen post).
TEMAS_RESPALDO: list[dict] = [
    {
        "id": "opinion-32d-negativa",
        "tema": "Opinión de cumplimiento 32-D negativa: qué la causa y cómo resolver cada motivo",
        "contexto": "",
        "categorias": ["cumplimiento-sat"],
        "gancho": "TodoConta descarga la 32-D de todas tus empresas y te pinta el semáforo con los motivos.",
        "fuente_ref": "Art. 32-D CFF; regla 2.1.37 RMF",
    },
    {
        "id": "errores-portal-sat",
        "tema": "Los errores más comunes del portal del SAT, traducidos: qué significan y qué hacer",
        "contexto": "",
        "categorias": ["cumplimiento-sat"],
        "gancho": "TodoConta reintenta y te avisa cuando el SAT falla — tú no peleas con el portal.",
        "fuente_ref": "Experiencia operativa con el portal del SAT",
    },
    {
        "id": "prestamo-socio-dividendo",
        "tema": "Préstamos a socios: cuándo el SAT los recalifica como dividendo ficto y qué documentar",
        "contexto": "",
        "categorias": ["regimenes", "cumplimiento-sat"],
        "gancho": "Ten el expediente de CFDI y estados de cuenta a la mano con TodoConta.",
        "fuente_ref": "LISR art. 140 (dividendo ficto)",
    },
    {
        "id": "conciliacion-plataformas",
        "tema": "Vendes por plataformas digitales: cómo conciliar lo que te retuvieron contra tus CFDI",
        "contexto": "",
        "categorias": ["impuestos-declaraciones"],
        "gancho": "Descarga todos tus CFDI del periodo y cruza retenciones en el procesador de TodoConta.",
        "fuente_ref": "LISR/LIVA retenciones de plataformas tecnológicas",
    },
    {
        "id": "papeles-trabajo-xml",
        "tema": "Papeles de trabajo desde tus XML: del ZIP del SAT al Excel que sí usas",
        "contexto": "",
        "categorias": ["contabilidad-despachos"],
        "gancho": "Los procesadores de TodoConta convierten miles de XML en un Excel profesional.",
        "fuente_ref": "",
    },
]


def _temas_del_calendario(hoy: datetime) -> list[dict]:
    """Filas con publicado=no del calendario editorial del repo, como temas.

    Solo considera filas cuya fecha_pub no quedó más de 7 días atrás (lo más
    viejo es coyuntura vencida: se deja en el CSV para que Israel decida).
    Ordenadas por fecha_pub — la primera es la siguiente a escribir.
    """
    crudo = github.leer_archivo(
        os.environ.get("CONTENIDO_REPO", REPO_DEFAULT),
        os.environ.get("CONTENIDO_CALENDARIO_RUTA", CALENDARIO_RUTA_DEFAULT),
    )
    if not crudo:
        return []
    temas: list[dict] = []
    try:
        for fila in csv.DictReader(io.StringIO(crudo)):
            if (fila.get("publicado") or "").strip().lower() == "si":
                continue
            titulo = (fila.get("titulo") or "").strip()
            fecha = (fila.get("fecha_pub") or "").strip()
            if not titulo or not fecha:
                continue
            try:
                fecha_pub = datetime.strptime(fecha, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if fecha_pub < hoy - timedelta(days=7):
                continue
            categoria = (fila.get("categoria") or "").strip()
            temas.append(
                {
                    "id": titulo,
                    "tema": titulo,
                    "contexto": (fila.get("contexto") or "").strip(),
                    "categorias": [categoria if categoria in CATEGORIAS_VALIDAS else "cumplimiento-sat"],
                    "gancho": (fila.get("producto_ligado") or "TodoConta Desktop").strip(),
                    "fuente_ref": (fila.get("fuente") or "").strip(),
                    "fecha_pub": fecha_pub.strftime("%Y-%m-%d"),
                }
            )
    except (csv.Error, KeyError) as e:
        print(f"[contenido] calendario ilegible ({e}) — uso el backlog de respaldo")
        return []
    return sorted(temas, key=lambda t: t["fecha_pub"])

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


def _elegir_tema(estado: dict, hoy: datetime) -> dict:
    """Siguiente tema: calendario editorial primero, backlog de respaldo después.

    `temas_usados` (por id/título en /data) evita repetir un tema ya generado
    aunque la fila del CSV siga con publicado=no (p. ej. si Israel todavía no
    la marca tras publicar).
    """
    usados = set(estado.get("temas_usados", []))
    del_calendario = [t for t in _temas_del_calendario(hoy) if t["id"] not in usados]
    if del_calendario:
        return del_calendario[0]
    print("[contenido] calendario sin pendientes (o no disponible) — backlog de respaldo")
    pendientes = [t for t in TEMAS_RESPALDO if t["id"] not in usados]
    if not pendientes:  # respaldo agotado → reinicia el ciclo del respaldo
        pendientes = TEMAS_RESPALDO
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

    tema = _elegir_tema(estado, hoy)
    modelo = os.environ.get("LLM_MODEL_CONTENIDO", "claude-sonnet-5")
    # La fecha planeada en el calendario manda; si ya pasó, el próximo miércoles.
    pub_date = tema.get("fecha_pub") or _proximo_miercoles(hoy)
    if pub_date < hoy.strftime("%Y-%m-%d"):
        pub_date = _proximo_miercoles(hoy)
    print(f"[contenido] semana {semana} — tema: {tema['id']}")

    brief = ""
    if tema.get("contexto"):
        brief += f"BRIEF EDITORIAL (síguelo — es el ángulo acordado): {tema['contexto']}\n"
    if tema.get("fuente_ref"):
        brief += (
            f"FUENTES DE REFERENCIA: {tema['fuente_ref']} (apóyate en ellas; "
            "lo que no puedas confirmar márcalo [VERIFICAR]).\n"
        )

    post = llm.generar(
        "Escribe un post de blog de 1,000-1,300 palabras sobre este tema:\n"
        f"TEMA: {tema['tema']}\n"
        + brief
        + f"PRODUCTO/HERRAMIENTA A LIGAR EN EL BLOQUE cta: {tema['gancho']} "
        "(si es solo un nombre de producto, redacta tú el copy del cta "
        "alrededor de él, siempre cerrando en descargar TodoConta Desktop).\n"
        f"MES ACTUAL: {hoy.strftime('%Y-%m')} (si el calendario fiscal mexicano "
        "tiene una fecha relevante cerca, úsala como percha; si no, no fuerces).\n"
        "El blog ya tiene 86+ posts publicados: no repitas guías básicas que "
        "seguramente existen (qué es un CFDI, qué es la DIOT); entra directo al "
        "ángulo del brief.\n\n"
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
            "- [ ] Marcar la fila como `publicado=si` en "
            "`apps/landing/editorial/calendario-editorial-2026.csv`\n"
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
