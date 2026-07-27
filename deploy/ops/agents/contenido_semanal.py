"""Borradores de contenido semanal → PR `drafts/semana-NN` en todoconta-apps.

Cada lunes genera con Claude (Sonnet) el paquete de contenido de la semana:

  drafts/semana-NN/YYYY-MM-DD-slug.md  post listo para mover al blog (spec de Israel)
  drafts/semana-NN/ficha-seo.md        palabra clave, título SEO, alt, prompt de imagen
  drafts/semana-NN/guion-video.md      guion de 5-8 min para el video de Israel

Los 3 posts sociales (LinkedIn, X/Threads, Facebook) NO viajan en el PR: se
crean como filas en la base de Notion "Contenido social — TodoConta"
(NOTION_DB_SOCIALES), una por red, en estado Borrador y con el copy completo en
el cuerpo de la página. Si Notion no está configurado o falla, caen como
`drafts/semana-NN/posts-sociales.md` para no perderse.

El boletín NO se genera aquí: la newsletter "Partida Doble" se arma con la
skill `/partida-doble` de todoconta-apps, que combina el post de la semana
(hero) con noticias, el anuncio y el offtopic. Este agente solo entrega el hero.

Gobernado por DOS archivos del repo de contenido, leídos en runtime vía la
GitHub API (editarlos NO requiere redeploy):
  - apps/landing/editorial/calendario-editorial-2026.csv — FUENTE de temas:
    toma la fila más próxima con publicado=no (brief, producto, fuentes).
  - apps/landing/editorial/instrucciones-blog.md — SPEC del post (SEO, quotes,
    encabezados, linking, mobile-first, serialización, Estilo 06, taxonomía).
Si alguno falta, cae a respaldos embebidos (backlog de temas / reglas mínimas).
Además lee el listado de apps/landing/src/content/blog para interlinkear con
slugs REALES y no reexplicar un tema que ya tiene post.

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
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lib import github, imagen, llm, notion

REDES = ("LinkedIn", "X/Threads", "Facebook")

ESTADO = Path("/data/contenido_estado.json")

REPO_DEFAULT = "soyisracastro/todoconta-apps"
CALENDARIO_RUTA_DEFAULT = "apps/landing/editorial/calendario-editorial-2026.csv"
INSTRUCCIONES_RUTA_DEFAULT = "apps/landing/editorial/instrucciones-blog.md"
BLOG_RUTA_DEFAULT = "apps/landing/src/content/blog"

# Resumen mínimo por si instrucciones-blog.md no está disponible (la versión
# completa y canónica vive en el repo de contenido y manda sobre esto).
REGLAS_RESPALDO = (
    "REGLAS DEL POST: palabra clave presente en el primer párrafo y 2-3 veces "
    "en total; slug evergreen de máx 4 palabras sin números; title visible + "
    "description ≤140 chars; 1-2 blockquotes destacados; 2-4 H2 con narrativa "
    "problema→solución→cierre; máx 3 referencias externas de fuentes oficiales "
    "(notas al pie [^1]) y 1-3 interlinks internos (/blog/INTERLINK:tema si no "
    "conoces el slug); párrafos de 2-3 oraciones (mobile-first); 800-1,200 "
    "palabras (máx 1,800); frontmatter SIN author, SIN cta, SIN isFeatured; "
    "heroImage /assets/blog/{slug}.jpg; categorías válidas: comprobantes-"
    "fiscales, impuestos-declaraciones, cumplimiento-sat, nomina-laboral, "
    "regimenes, contabilidad-despachos, ia-tecnologia; tags 3-5 en Title Case."
)

CATEGORIAS_VALIDAS = {
    "comprobantes-fiscales",
    "impuestos-declaraciones",
    "cumplimiento-sat",
    "nomina-laboral",
    "regimenes",
    "contabilidad-despachos",
    "ia-tecnologia",
}

# Backlog de RESPALDO (dolores reales de todoconta-apps docs/negocio/abacus-oportunidades-producto.md
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

def _posts_publicados() -> list[str]:
    """Slugs REALES del blog, del más nuevo al más viejo.

    El slug de un post es su nombre de archivo sin la fecha (`getPostSlug` en
    apps/landing/src/lib/utils.ts hace `replace(/^\\d{4}-\\d{2}-\\d{2}-/, "")`),
    así que `2026-07-02-listas-negras-sat-efos.md` vive en
    /blog/listas-negras-sat-efos.
    """
    archivos = github.listar_directorio(
        os.environ.get("CONTENIDO_REPO", REPO_DEFAULT),
        os.environ.get("CONTENIDO_BLOG_RUTA", BLOG_RUTA_DEFAULT),
    )
    posts = sorted((a for a in archivos if a.endswith((".md", ".mdx"))), reverse=True)
    return [re.sub(r"^\d{4}-\d{2}-\d{2}-", "", a).rsplit(".", 1)[0] for a in posts]


def _parsear_sociales(crudo: str) -> list[dict]:
    """Separa el bloque de sociales por sus marcadores `--- Red ---`.

    Marcadores y no JSON a propósito: el copy es multilínea (el hilo de X son
    varios tuits) y un salto de línea sin escapar rompe cualquier json.loads.
    """
    patron = re.compile(
        r"^[-*\s]*(?:\*\*)?\s*(" + "|".join(re.escape(r) for r in REDES) + r")"
        r"\s*(?:\*\*)?[-*\s]*$",
        re.IGNORECASE | re.MULTILINE,
    )
    marcas = list(patron.finditer(crudo))
    sociales: list[dict] = []
    for i, marca in enumerate(marcas):
        fin = marcas[i + 1].start() if i + 1 < len(marcas) else len(crudo)
        copy = crudo[marca.end() : fin].strip()
        red = next(r for r in REDES if r.lower() == marca.group(1).lower())
        if copy and not any(s["red"] == red for s in sociales):
            sociales.append({"red": red, "copy": copy})
    return sociales


def _publicar_sociales(
    sociales: list[dict], *, semana: str, tema: str, url_post: str, url_pr: str
) -> int:
    """Una fila por red en la base de Notion. Devuelve cuántas se crearon.

    Best-effort: sin NOTION_API_KEY/NOTION_DB_SOCIALES (o si la API falla) el
    llamador conserva el .md dentro del PR como respaldo.
    """
    db_id = os.environ.get("NOTION_DB_SOCIALES")
    if not (db_id and os.environ.get("NOTION_API_KEY")):
        print("[contenido] sin NOTION_DB_SOCIALES/NOTION_API_KEY — sociales al .md")
        return 0
    creadas = 0
    for social in sociales:
        url = notion.crear_pagina(
            db_id,
            {
                "Post": notion.titulo(f"{semana} · {social['red']} · {tema[:60]}"),
                "Red": {"select": {"name": social["red"]}},
                "Semana": notion.texto(semana),
                "Estado": {"select": {"name": "Borrador"}},
                "Caracteres": {"number": len(social["copy"])},
                "Post del blog": {"url": url_post},
                "Tema": notion.texto(tema),
                "Origen": {"url": url_pr} if url_pr else {"url": None},
            },
            cuerpo=social["copy"],
        )
        if url:
            creadas += 1
            print(f"[contenido] Notion ← {social['red']}: {url}")
    return creadas


def _avisos(post: str, slug: str) -> list[str]:
    """Defectos mecánicos del post que Israel tiene que revisar a mano.

    No abortan la corrida (el borrador igual sirve): se listan en el cuerpo del
    PR para que salten a la vista en vez de colarse a producción — como pasó en
    la semana 2026-30 con un `[VERIFICAR]` publicado como prosa.
    """
    avisos: list[str] = []
    if "[VERIFICAR]" in post:
        avisos.append(
            "El post trae `[VERIFICAR]` en el texto: resuelve el dato o borra la "
            "nota — **nunca debe publicarse así**."
        )
    if "INTERLINK:" in post:
        avisos.append(
            "Quedaron interlinks con placeholder `INTERLINK:`: cámbialos por un "
            "slug real de `/blog/` o quita el enlace."
        )
    desc = re.search(r"^description:\s*\"(.*)\"\s*$", post, re.MULTILINE)
    if desc and len(desc.group(1)) > 140:
        avisos.append(
            f"`description` de {len(desc.group(1))} caracteres (máx 140): recórtala."
        )
    # instrucciones-blog.md pide 800-1,200, pero los posts que Israel publica
    # andan en 665-736 (listas-negras 736, renovar-efirma 665). El aviso salta
    # en 600 para marcar lo genuinamente flaco en vez de gritar cada semana;
    # el prompt sigue pidiendo el rango de la spec.
    palabras = len(post.split("---", 2)[-1].split())
    if palabras < 600:
        avisos.append(f"El cuerpo trae ~{palabras} palabras: quedó corto, amplíalo.")
    if f"/assets/blog/{slug}.jpg" not in post:
        avisos.append(f"El `heroImage` del frontmatter no apunta a `{slug}.jpg`.")
    return avisos


SISTEMA = (
    "Eres el redactor de contenido de TodoConta (todoconta.com), una app de "
    "escritorio para contadores en México que automatiza la descarga masiva de "
    "CFDI y documentos del SAT (constancia de situación fiscal, opinión 32-D, "
    "DIOT), con procesadores que convierten XML en Excel y calculadoras "
    "fiscales. Precios: prueba gratis 15 días; plan Anual $2,990 MXN; Anual con "
    "IA $4,990 MXN. Escribes en español de México, directo y sin relleno, con "
    "la voz de Israel Castro (contador que construye software): práctico, "
    "honesto, cero humo. "
    "Reglas de copy INNEGOCIABLES — gobiernan CÓMO escribes; son instrucciones "
    "para ti, NUNCA las describas ni las menciones dentro del texto: di "
    "«Contraseña del SAT (antes CIEC)» en la primera mención y «Contraseña» "
    "después, nunca «CIEC» a secas; nunca uses la palabra «espejo» para la "
    "versión web (di «versión web»); la promesa de privacidad es «tú decides "
    "dónde viven tus datos». "
    "NUNCA inventes el nombre de un módulo de la app: los que existen son "
    "Inicio, Tareas, Empresas, Descargar CFDIs, Comprobantes, Listas negras "
    "(cruce contra las listas 69 y 69-B del SAT — NO se llama «Auditoría "
    "EFOS»), Organizador, Historial, Calculadoras, DIOT, Ayuda y Ajustes. Si el "
    "brief te sugiere otro nombre, usa el de esta lista que le corresponda. "
    "No inventes cifras, artículos de ley ni fechas límite. Si no puedes "
    "confirmar un dato normativo NO lo escribas en el cuerpo del post: omítelo "
    "y repórtalo en el campo `pendientes_verificar` de la ficha. El cuerpo del "
    "post es texto publicable — jamás debe contener la marca [VERIFICAR] ni "
    "notas dirigidas al editor."
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

    instrucciones = github.leer_archivo(
        os.environ.get("CONTENIDO_REPO", REPO_DEFAULT),
        os.environ.get("CONTENIDO_INSTRUCCIONES_RUTA", INSTRUCCIONES_RUTA_DEFAULT),
    )
    if instrucciones:
        reglas = (
            "INSTRUCCIONES CANÓNICAS DEL BLOG (mandan sobre cualquier otra "
            "indicación de formato):\n\n" + instrucciones
        )
    else:
        print("[contenido] instrucciones-blog.md no disponible — reglas embebidas")
        reglas = REGLAS_RESPALDO

    # Slugs reales del blog: sin esto el modelo inventa interlinks (semana
    # 2026-30 enlazó a /blog/requerimientos-sat-cfdi, que nunca existió) y
    # reexplica desde cero temas que ya tienen post.
    publicados = _posts_publicados()
    if publicados:
        catalogo = (
            "POSTS YA PUBLICADOS (slug real de cada uno — la URL es "
            "https://todoconta.com/blog/<slug>):\n"
            + "\n".join(f"- {s}" for s in publicados)
            + "\n\nÚSALOS ASÍ: (a) NO reexpliques desde cero un tema que ya "
            "tiene post — dalo por leído, enlázalo en una línea y dedica el "
            "cuerpo a lo que este post aporta de nuevo; (b) los 1-3 interlinks "
            "internos deben apuntar a un slug DE ESTA LISTA, escrito completo "
            "como /blog/<slug>. Solo si ninguno aplica usa el placeholder "
            "/blog/INTERLINK:tema.\n\n"
        )
    else:
        print("[contenido] no pude listar el blog — interlinks con placeholder")
        catalogo = ""

    crudo = llm.generar(
        f"{reglas}\n\n"
        "════════\n"
        + catalogo
        + "Genera el post de esta semana siguiendo esas instrucciones.\n"
        f"TEMA: {tema['tema']}\n"
        + brief
        + f"CATEGORÍA SUGERIDA POR EL CALENDARIO: {json.dumps(tema['categorias'])} "
        "(decide primaria/secundaria con la sección 8).\n"
        f"PRODUCTO/HERRAMIENTA A LIGAR: {tema['gancho']} — cierre suave DENTRO "
        "del cuerpo: el último párrafo invita a resolverlo con esa herramienta "
        "de TodoConta Desktop enlazando a https://todoconta.com/descargar. "
        "Recuerda: el frontmatter NO lleva bloque cta.\n"
        f"pubDate: {pub_date}\n"
        f"MES ACTUAL: {hoy.strftime('%Y-%m')} (si el calendario fiscal mexicano "
        "tiene una fecha relevante cerca, úsala como percha; si no, no fuerces).\n"
        "El blog ya rebasa los 85 posts: no repitas guías básicas.\n"
        "CONTROLES QUE SE VALIDAN DESPUÉS (si fallan, el borrador se devuelve): "
        "`description` de MÁXIMO 140 caracteres — apunta a 120-135 para tener "
        "margen y cuéntalos antes de responder; cuerpo de 800 a 1,200 "
        "palabras; cero `[VERIFICAR]` y cero notas al editor en el cuerpo.\n\n"
        "RESPONDE EXACTAMENTE con dos secciones y nada más:\n"
        "=== FICHA ===\n"
        "Un objeto JSON con: palabra_clave, slug, titulo_seo (≤60 chars, con la "
        "palabra clave), alt (descripción de la heroImage, con la palabra "
        "clave), prompt_imagen (el prompt Estilo 06 completo, con [SUBJECT] ya "
        "resuelto para este post), pendientes_verificar (lista de strings: los "
        "datos normativos que NO pudiste confirmar y por eso dejaste fuera del "
        "cuerpo; [] si no hay), plan_serie (null; o, si el material rebasa "
        "1,800 palabras, {\"articulos\": [\"título 1\", …], \"razon\": \"…\"}).\n"
        "=== POST ===\n"
        "El archivo Markdown completo, empezando por el frontmatter YAML "
        "(title, description, pubDate, heroImage \"/assets/blog/<slug>.jpg\", "
        "categories, tags) — sin fences de código alrededor.",
        sistema=SISTEMA,
        modelo=modelo,
        # En Sonnet 5 max_tokens cubre thinking + texto. Con 6000 el thinking
        # se lo comía entero y el post salía vacío; 16000 es el techo cómodo
        # sin streaming (arriba de eso arriesgas timeout de HTTP).
        max_tokens=16000,
        # "high" y no "medium": el esfuerzo bajo acorta la salida (con medium
        # el post salió de 655 palabras contra el mínimo de 800) y aquí la
        # extensión es parte del entregable.
        esfuerzo="high",
    )
    if not crudo or "=== POST ===" not in crudo:
        print("[contenido] Claude no devolvió ficha+post — abortando")
        return 1

    ficha_cruda, post = (p.strip() for p in crudo.split("=== POST ===", 1))
    ficha_cruda = ficha_cruda.split("=== FICHA ===", 1)[-1].strip()
    if ficha_cruda.startswith("```"):
        ficha_cruda = ficha_cruda.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    if post.startswith("```"):
        post = post.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        ficha = json.loads(ficha_cruda)
    except ValueError:
        print("[contenido] ficha ilegible — sigo sin ella")
        ficha = {}

    # Slug saneado (evergreen: minúsculas, guiones, sin números — regla 4b).
    base = str(ficha.get("slug") or tema["tema"]).lower().replace("-", " ")
    palabras = [
        "".join(c for c in p if c.isalnum() and not c.isdigit()) for p in base.split()
    ]
    slug = "-".join([p for p in palabras if p][:4]) or "post-semanal"

    # El correo NO sale de aquí: la newsletter (Partida Doble) se arma con la
    # skill `/partida-doble` de todoconta-apps, que mezcla el post con noticias,
    # el anuncio y el offtopic de la semana. Este agente solo entrega el post
    # que esa skill usa como hero.
    url_post = f"https://todoconta.com/blog/{slug}"
    derivados = llm.generar(
        "A partir de este post de blog, genera las piezas derivadas de la "
        "semana. Responde EXACTAMENTE con dos secciones separadas por líneas "
        "'=== GUION ===' y '=== SOCIALES ==='.\n\n"
        "1) GUION: guion de video de 5-8 minutos para YouTube (Israel a "
        "cámara): hook de 15 segundos, desarrollo en 3 bloques con las ideas "
        "del post (indicaciones de pantalla entre corchetes cuando ayude), y "
        "cierre con CTA a descargar TodoConta Desktop. Tono conversacional, "
        "frases cortas para teleprompter.\n"
        "2) SOCIALES: 3 posts listos para pegar, cada uno precedido por su "
        "marcador EN UNA LÍNEA SOLA y en este orden exacto:\n"
        "--- LinkedIn ---\n(150-220 palabras, gancho fuerte en la primera "
        "línea, sin hashtags spam, máx 3)\n"
        "--- X/Threads ---\n(hilo corto de 3-4 tuits numerados)\n"
        "--- Facebook ---\n(100-150 palabras, tono cercano)\n"
        "Sin encabezados ni comentarios extra entre ellos. Cada uno cierra con "
        f"el enlace {url_post} — escríbelo TAL CUAL, sin placeholders.\n\n"
        f"POST:\n{post}",
        sistema=SISTEMA,
        modelo=modelo,
        # Mismo cuidado que arriba; esfuerzo bajo porque es reescritura de un
        # post que ya existe, no creación.
        max_tokens=12000,
        esfuerzo="low",
    )
    if not derivados:
        print("[contenido] Claude no devolvió las piezas derivadas — abortando")
        return 1

    partes: dict[str, str] = {}
    for marca in ("=== GUION ===", "=== SOCIALES ==="):
        if marca not in derivados:
            print(f"[contenido] falta la sección {marca} — abortando")
            return 1
    _, tras_guion = derivados.split("=== GUION ===", 1)
    partes["guion"], partes["sociales"] = tras_guion.split("=== SOCIALES ===", 1)

    sociales = _parsear_sociales(partes["sociales"])
    if not sociales:
        print("[contenido] sociales ilegibles — van como .md en el PR")

    plan_serie = ficha.get("plan_serie")
    pendientes = [str(p) for p in (ficha.get("pendientes_verificar") or []) if p]
    modelo_img = os.environ.get("GEMINI_IMAGE_MODEL", imagen.MODELO_DEFAULT)
    ficha_md = (
        f"# Ficha SEO e imagen — semana {semana}\n\n"
        f"- **Tema:** {tema['tema']}\n"
        f"- **Palabra clave:** {ficha.get('palabra_clave', '[PENDIENTE]')}\n"
        f"- **Slug:** `{slug}`\n"
        f"- **URL del post:** {url_post}\n"
        f"- **Título SEO (≤60):** {ficha.get('titulo_seo', '[PENDIENTE]')}\n"
        f"- **Alt de la heroImage:** {ficha.get('alt', '[PENDIENTE]')}\n"
        f"- **heroImage:** `/assets/blog/{slug}.jpg` (16:9, fondo #FAFAF7)\n\n"
        "## Prompt de imagen (Estilo 06 — isométrico minimalista)\n\n"
        f"```\n{ficha.get('prompt_imagen', '[PENDIENTE — usar el prompt base de instrucciones-blog.md §7]')}\n```\n\n"
        f"Generar con Gemini (`{modelo_img}`, 16:9) → comprimir "
        "(scripts/convert-images.py con TinyPNG) → guardar como "
        f"`apps/landing/public/assets/blog/{slug}.jpg`.\n"
        + (
            "\n## ⚠️ Datos normativos por verificar\n\n"
            "Se dejaron FUERA del post a propósito. Si los confirmas, valen un "
            "párrafo extra:\n\n"
            + "".join(f"- {p}\n" for p in pendientes)
            if pendientes
            else ""
        )
        + (
            "\n## ⚠️ Plan de serie sugerido (el material rebasa 1,800 palabras)\n\n"
            f"{json.dumps(plan_serie, ensure_ascii=False, indent=2)}\n"
            if plan_serie
            else ""
        )
    )

    carpeta = f"drafts/semana-{semana}"
    sociales_md = f"{carpeta}/posts-sociales.md"
    respaldo_sociales = (
        f"# Posts sociales — semana {semana}\n\n"
        + (
            "\n\n---\n\n".join(
                f"**{s['red'].upper()}**\n\n{s['copy']}" for s in sociales
            )
            or partes["sociales"].strip()
        )
        + "\n"
    )
    archivos = {
        f"{carpeta}/{pub_date}-{slug}.md": post.strip() + "\n",
        f"{carpeta}/ficha-seo.md": ficha_md,
        f"{carpeta}/guion-video.md": (
            f"# Guion de video — semana {semana}\n\nTema: {tema['tema']}\n\n"
            + partes["guion"].strip()
            + "\n"
        ),
    }
    # Los sociales viven en Notion; el .md solo entra si Notion no está en juego
    # (sin envs, o sociales ilegibles) para no perder el copy.
    notion_listo = bool(
        sociales
        and os.environ.get("NOTION_DB_SOCIALES")
        and os.environ.get("NOTION_API_KEY")
    )
    if not notion_listo:
        archivos[sociales_md] = respaldo_sociales

    if dry_run:
        for ruta, contenido in archivos.items():
            print(f"\n───── {ruta} ─────\n{contenido}")
        if notion_listo:
            # No van al PR (viven en Notion), pero en seco hay que poder verlos.
            print(f"\n───── Notion · Contenido social ─────\n{respaldo_sociales}")
        print("(dry-run: la heroImage no se genera para no gastar API)")
        return 0

    # heroImage automática (Gemini económico → TinyPNG → JPG en el mismo PR).
    # Best-effort: sin keys o con fallo, el PR sale sin imagen y la ficha
    # conserva el prompt para generarla a mano.
    hero_incluida = False
    prompt_img = str(ficha.get("prompt_imagen") or "")
    if prompt_img:
        png = imagen.generar_hero(prompt_img)
        jpg = imagen.comprimir_jpg(png) if png else None
        if jpg:
            archivos[f"apps/landing/public/assets/blog/{slug}.jpg"] = jpg
            hero_incluida = True
            print(f"[contenido] heroImage generada e incluida ({len(jpg) // 1024} KB)")
        else:
            print("[contenido] sin heroImage automática — la ficha trae el prompt")

    linea_hero = (
        f"- [ ] Revisar la heroImage incluida (`public/assets/blog/{slug}.jpg`)\n"
        if hero_incluida
        else "- [ ] Generar la heroImage con el prompt de `ficha-seo.md` "
        f"(Gemini → tinypng → `public/assets/blog/{slug}.jpg`)\n"
    )

    avisos = _avisos(post, slug)
    bloque_avisos = (
        "\n> [!WARNING]\n> **Revisar antes de publicar:**\n"
        + "".join(f"> - {a}\n" for a in avisos)
        + "\n"
        if avisos
        else ""
    )

    url = github.crear_pr_con_archivos(
        repo=os.environ.get("CONTENIDO_REPO", REPO_DEFAULT),
        rama=f"drafts/semana-{semana}",
        titulo=f"drafts: semana {semana} — {tema['tema'][:60]}",
        cuerpo=(
            f"Paquete de contenido de la semana {semana}, generado por el agente "
            "`contenido_semanal` (deploy/ops). **Nada de esto se publica al "
            "mergear** — los archivos viven en `drafts/`.\n\n"
            f"**Tema:** {tema['tema']}\n"
            f"**URL final:** {url_post}\n"
            + bloque_avisos
            + "\nChecklist de Israel:\n"
            f"- [ ] Revisar/editar `{pub_date}-{slug}.md` y moverlo tal cual a "
            "`apps/landing/src/content/blog/`\n"
            + linea_hero
            + "- [ ] Marcar la fila como `publicado=si` en "
            "`apps/landing/editorial/calendario-editorial-2026.csv`\n"
            "- [ ] Grabar el video con `guion-video.md` (miércoles)\n"
            + (
                "- [ ] Programar los 3 posts de la base **Contenido social** "
                "en Notion (llegan en `Borrador`)\n"
                if notion_listo
                else "- [ ] Programar `posts-sociales.md`\n"
            )
            + "- [ ] Armar el boletín con `/partida-doble` usando este post como "
            "hero (el correo NO sale de este PR)\n\n"
            "🤖 Generado por deploy/ops/agents/contenido_semanal.py"
        ),
        archivos=archivos,
    )

    # Los sociales van a Notion (una fila por red). Si no se creó ninguna, el
    # copy se sube como .md a la misma rama para no perderlo.
    if notion_listo:
        creadas = _publicar_sociales(
            sociales,
            semana=semana,
            tema=tema["tema"],
            url_post=url_post,
            url_pr=url,
        )
        if creadas < len(sociales):
            print(f"[contenido] Notion creó {creadas}/{len(sociales)} — subo el .md")
            github.crear_pr_con_archivos(
                repo=os.environ.get("CONTENIDO_REPO", REPO_DEFAULT),
                rama=f"drafts/semana-{semana}",
                titulo=f"drafts: semana {semana} — {tema['tema'][:60]}",
                cuerpo="",
                archivos={sociales_md: respaldo_sociales},
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
