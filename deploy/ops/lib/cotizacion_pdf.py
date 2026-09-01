"""Genera el PDF de una cotización de marca TodoConta.

Porta la plantilla HTML ya aprobada (paleta del design-system: primary #0B5FFF,
foreground #0A1628, Inter + JetBrains Mono) y la renderiza a bytes PDF con
Chromium headless vía Playwright. Las fuentes se **embeben como data-URI** para
que el render sea determinista y offline (sin depender de Google Fonts ni de
fuentes del sistema en el contenedor slim).

API:
    total_de(items) -> float
    construir_html(datos) -> str      # útil para inspección / pruebas sin Chromium
    render(datos) -> bytes            # HTML -> PDF (requiere Playwright + Chromium)

`datos` es un dict:
    {
      "emisor": {...},               # data/emisor.json
      "folio": "COT-NOMITEK-2026-08",
      "fecha": "05 de agosto de 2026",
      "vigenciaDias": 15,
      "cliente": {"nombre","atencion"(opc),"email","rfc"(opc)},
      "items": [{"concepto","cantidad","precioUnitario"}, ...],
      "notaIva": "..."(opc),
      "condiciones": [...](opc),      # default: emisor["condicionesDefault"]
    }
"""

from __future__ import annotations

import base64
import html as html_mod
from functools import lru_cache
from pathlib import Path

# /app/lib/cotizacion_pdf.py -> base = /app ; fuentes en /app/assets/fonts
_BASE = Path(__file__).resolve().parent.parent
_FONTS = _BASE / "assets" / "fonts"


@lru_cache(maxsize=8)
def _font_data_uri(nombre: str) -> str:
    datos = (_FONTS / nombre).read_bytes()
    b64 = base64.b64encode(datos).decode("ascii")
    return f"data:font/woff2;base64,{b64}"


def _escape(valor: object) -> str:
    return html_mod.escape(str(valor), quote=True)


def _money(monto: float) -> str:
    """$1,234.56 con separador de miles y 2 decimales."""
    return "$" + f"{monto:,.2f}"


def total_de(items: list[dict]) -> float:
    return sum(float(it["cantidad"]) * float(it["precioUnitario"]) for it in items)


def _bloque_fuentes() -> str:
    inter = _font_data_uri("InterVariable.woff2")
    jb500 = _font_data_uri("JetBrainsMono-500.woff2")
    jb600 = _font_data_uri("JetBrainsMono-600.woff2")
    return f"""
    @font-face {{
      font-family: "Inter"; font-style: normal; font-weight: 100 900;
      font-display: block; src: url({inter}) format("woff2");
    }}
    @font-face {{
      font-family: "JetBrains Mono"; font-style: normal; font-weight: 500;
      font-display: block; src: url({jb500}) format("woff2");
    }}
    @font-face {{
      font-family: "JetBrains Mono"; font-style: normal; font-weight: 600;
      font-display: block; src: url({jb600}) format("woff2");
    }}
    """


def construir_html(datos: dict) -> str:
    emisor = datos["emisor"]
    cliente = datos["cliente"]
    items = datos["items"]
    vigencia = datos.get("vigenciaDias", emisor.get("vigenciaDias", 15))
    nota_iva = datos.get("notaIva") or emisor.get(
        "notaIva", "Precios en pesos mexicanos (MXN), IVA incluido."
    )
    condiciones = datos.get("condiciones") or emisor.get("condicionesDefault", [])
    banco = emisor["banco"]
    total = total_de(items)

    filas = "".join(
        f"""
        <tr>
          <td>{_escape(it["concepto"])}</td>
          <td class="num mono">{_escape(it["cantidad"])}</td>
          <td class="num mono">{_escape(_money(float(it["precioUnitario"])))}</td>
          <td class="num mono">{_escape(_money(float(it["cantidad"]) * float(it["precioUnitario"])))}</td>
        </tr>"""
        for it in items
    )

    lista_cond = "".join(f"<li>{_escape(c)}</li>" for c in condiciones)

    atencion = (
        f'<p>Atención: {_escape(cliente["atencion"])}</p>'
        if cliente.get("atencion")
        else ""
    )
    cliente_rfc = (
        f'<p class="mono">RFC: {_escape(cliente["rfc"])}</p>'
        if cliente.get("rfc")
        else ""
    )
    # Nombre corto del emisor para el pie (primeras 2 palabras).
    pie_nombre = " ".join(str(emisor["nombre"]).split()[:2])

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Cotización {_escape(cliente["nombre"])}</title>
<style>
  {_bloque_fuentes()}
  @page {{ size: A4; margin: 0; }}
  * {{ box-sizing: border-box; }}
  :root {{
    --primary: #0B5FFF; --foreground: #0A1628; --card: #FFFFFF;
    --muted: #F0F3F8; --muted-foreground: #56677F; --border: #E5ECF4;
  }}
  body {{
    margin: 0; font-family: "Inter", -apple-system, "Helvetica Neue", Arial, sans-serif;
    color: var(--foreground); font-size: 13px; line-height: 1.5; background: var(--card);
    -webkit-print-color-adjust: exact; print-color-adjust: exact;
  }}
  .mono {{ font-family: "JetBrains Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace; font-variant-numeric: tabular-nums; }}
  .page {{ width: 210mm; min-height: 297mm; padding: 18mm 20mm; }}
  .header {{
    display: flex; justify-content: space-between; align-items: flex-start;
    border-bottom: 3px solid var(--primary); padding-bottom: 14px; margin-bottom: 26px;
  }}
  .brand {{ font-size: 22px; font-weight: 800; color: var(--foreground); letter-spacing: 0.2px; }}
  .brand-sub {{ font-size: 11px; color: var(--muted-foreground); margin-top: 2px; }}
  .doc-title {{ text-align: right; }}
  .doc-title h1 {{ font-size: 18px; margin: 0 0 4px 0; color: var(--primary); letter-spacing: 1px; font-weight: 800; }}
  .doc-meta {{ font-size: 11.5px; color: var(--muted-foreground); }}
  .doc-meta div {{ margin-bottom: 1px; }}
  .doc-meta .mono {{ color: var(--foreground); }}
  .parties {{ display: flex; justify-content: space-between; gap: 24px; margin-bottom: 28px; }}
  .party {{ flex: 1; background: var(--muted); border-radius: 8px; padding: 12px 16px; }}
  .party h3 {{ font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.6px; color: var(--muted-foreground); margin: 0 0 6px 0; font-weight: 700; }}
  .party p {{ margin: 0; }}
  .party .name {{ font-weight: 700; font-size: 13.5px; color: var(--foreground); }}
  table.items {{ width: 100%; border-collapse: collapse; margin-bottom: 6px; }}
  table.items thead th {{
    background: var(--primary); color: #fff; text-align: left; padding: 9px 12px;
    font-size: 11px; text-transform: uppercase; letter-spacing: 0.4px; font-weight: 700;
  }}
  table.items thead th.num {{ text-align: right; }}
  table.items tbody td {{ padding: 11px 12px; border-bottom: 1px solid var(--border); }}
  table.items tbody td.num {{ text-align: right; }}
  table.items tfoot td {{ padding: 10px 12px; font-weight: 700; }}
  table.items tfoot td.num {{ text-align: right; font-size: 14.5px; color: var(--primary); white-space: nowrap; }}
  .note-iva {{ font-size: 11px; color: var(--muted-foreground); margin: 4px 0 26px 0; }}
  .cols {{ display: flex; gap: 24px; margin-bottom: 24px; }}
  .box {{ flex: 1; border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px; }}
  .box h3 {{
    font-size: 11px; text-transform: uppercase; letter-spacing: 0.6px; color: var(--muted-foreground);
    margin: 0 0 8px 0; border-bottom: 1px solid var(--border); padding-bottom: 6px; font-weight: 700;
  }}
  .bank-row {{ display: flex; justify-content: space-between; margin-bottom: 4px; }}
  .bank-row .k {{ color: var(--muted-foreground); }}
  .bank-row .v {{ font-weight: 600; text-align: right; }}
  .terms ul {{ margin: 0; padding-left: 18px; }}
  .terms li {{ margin-bottom: 5px; }}
  .footer {{
    margin-top: 30px; padding-top: 14px; border-top: 1px solid var(--border);
    display: flex; justify-content: space-between; font-size: 11px; color: var(--muted-foreground);
  }}
</style>
</head>
<body>
  <div class="page">
    <div class="header">
      <div>
        <div class="brand">{_escape(emisor["marca"])}</div>
        <div class="brand-sub">{_escape(emisor["submarca"])} · {_escape(emisor["nombre"])}</div>
      </div>
      <div class="doc-title">
        <h1>COTIZACIÓN</h1>
        <div class="doc-meta">
          <div>Folio: <span class="mono">{_escape(datos["folio"])}</span></div>
          <div>Fecha: {_escape(datos["fecha"])}</div>
          <div>Vigencia: {_escape(vigencia)} días naturales</div>
        </div>
      </div>
    </div>

    <div class="parties">
      <div class="party">
        <h3>Emite</h3>
        <p class="name">{_escape(emisor["nombre"])}</p>
        <p class="mono">RFC: {_escape(emisor["rfc"])}</p>
        <p>WhatsApp: {_escape(emisor["whatsapp"])}</p>
        <p>{_escape(emisor["web"])}</p>
      </div>
      <div class="party">
        <h3>Cliente</h3>
        <p class="name">{_escape(cliente["nombre"])}</p>
        {atencion}
        <p>{_escape(cliente.get("email", ""))}</p>
        {cliente_rfc}
      </div>
    </div>

    <table class="items">
      <thead>
        <tr>
          <th>Concepto</th>
          <th class="num">Cantidad</th>
          <th class="num">Precio unitario</th>
          <th class="num">Importe</th>
        </tr>
      </thead>
      <tbody>{filas}
      </tbody>
      <tfoot>
        <tr>
          <td colspan="3">Total</td>
          <td class="num mono">{_escape(_money(total))} MXN</td>
        </tr>
      </tfoot>
    </table>
    <p class="note-iva">{_escape(nota_iva)}</p>

    <div class="cols">
      <div class="box">
        <h3>Datos para pago</h3>
        <div class="bank-row"><span class="k">Banco</span><span class="v">{_escape(banco["nombre"])}</span></div>
        <div class="bank-row"><span class="k">Beneficiario</span><span class="v">{_escape(banco["beneficiario"])}</span></div>
        <div class="bank-row"><span class="k">RFC</span><span class="v mono">{_escape(banco["rfc"])}</span></div>
        <div class="bank-row"><span class="k">Cuenta</span><span class="v mono">{_escape(banco["cuenta"])}</span></div>
        <div class="bank-row"><span class="k">CLABE</span><span class="v mono">{_escape(banco["clabe"])}</span></div>
      </div>
      <div class="box">
        <h3>Condiciones</h3>
        <div class="terms"><ul>{lista_cond}</ul></div>
      </div>
    </div>

    <div class="footer">
      <div>{_escape(emisor["marca"])} · {_escape(pie_nombre)}</div>
      <div>Cotización válida por {_escape(vigencia)} días naturales</div>
    </div>
  </div>
</body>
</html>
"""


def render(datos: dict) -> bytes:
    """Construye el HTML y lo renderiza a bytes PDF con Chromium (Playwright)."""
    from playwright.sync_api import sync_playwright  # import lazy (extra ciec)

    html = construir_html(datos)
    with sync_playwright() as p:
        navegador = p.chromium.launch(args=["--no-sandbox"])
        try:
            pagina = navegador.new_page()
            pagina.set_content(html, wait_until="load")
            # Asegura que las @font-face embebidas terminen de cargar antes del PDF.
            pagina.evaluate("async () => { await document.fonts.ready; }")
            return pagina.pdf(
                format="A4", print_background=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            )
        finally:
            navegador.close()
