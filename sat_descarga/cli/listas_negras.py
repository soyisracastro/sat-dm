"""
CLI: sat-dm listas-negras — Validación de RFCs contra las listas del SAT
(Art. 69 y 69-B del CFF) consumiendo la API de todoconta-apps.

Tres modos:
  --rfc XXX                 → consulta un solo RFC
  --archivo rfcs.txt        → lee RFCs (1 por línea o separados por coma) de un archivo
  --desde-procesador        → cruza con el buffer del procesador (todos los emisores
                              y receptores cargados) — útil para detectar EDOS

Requiere sesión iniciada en la app (Bearer guardado en el keyring).
"""

import csv
import re

import click

from .display import print_header, print_success, print_warning, print_error


_RFC_SPLIT = re.compile(r"[\s,;\n\r\t]+")


@click.command("listas-negras")
@click.option("--rfc", "rfc_unico", default=None, help="Un solo RFC a consultar")
@click.option(
    "--archivo", "-a",
    type=click.Path(exists=True),
    default=None,
    help="Archivo con RFCs (uno por línea o separados por coma/tab)",
)
@click.option(
    "--desde-procesador",
    is_flag=True,
    default=False,
    help="Toma los RFCs (emisor + receptor) del buffer del procesador",
)
@click.option(
    "--force-refresh",
    is_flag=True,
    default=False,
    help="Ignora el TTL de 30 días al usar --desde-procesador",
)
@click.option(
    "--salida", "-o",
    type=click.Path(),
    default=None,
    help="Archivo CSV de salida con resultados",
)
def listas_negras(rfc_unico, archivo, desde_procesador, force_refresh, salida):
    """
    Valida RFCs contra las listas negras del SAT (Art. 69 y 69-B).

    EFOS  = RFC en lista 69-B con situación Definitivo o Presunto.
    EDOS  = receptor de un CFDI cuyo emisor es EFOS (al cruzar con el buffer).

    Requiere sesión iniciada en la app desktop (Bearer en keyring).
    """
    from ..utils.listas_negras import consultar_rfcs, clasificar

    print_header("Listas negras del SAT (Art. 69 y 69-B)")

    rfcs = _recopilar_rfcs(rfc_unico, archivo, desde_procesador, force_refresh)
    if not rfcs:
        print_warning("No hay RFCs para consultar.")
        return

    click.echo(f"  RFCs a consultar: {len(rfcs)}")
    click.echo()

    try:
        with click.progressbar(
            length=len(rfcs), label="  Consultando", show_pos=True,
        ) as bar:
            matches, metadata = consultar_rfcs(rfcs)
            bar.update(len(rfcs))
    except RuntimeError as e:
        click.echo()
        print_error(str(e))
        return

    click.echo()

    # Resumen por etiqueta
    contadores = {"EFOS": 0, "Aclarado": 0, "69": 0, "Limpio": 0}
    for m in matches:
        contadores[clasificar(m)] += 1

    print_error(f"EFOS:         {contadores['EFOS']}") if contadores["EFOS"] else click.echo(f"  EFOS:         {contadores['EFOS']}")
    print_warning(f"Aclarados:    {contadores['Aclarado']}") if contadores["Aclarado"] else click.echo(f"  Aclarados:    {contadores['Aclarado']}")
    if contadores["69"]:
        print_warning(f"En lista 69:  {contadores['69']}")
    else:
        click.echo(f"  En lista 69:  {contadores['69']}")
    print_success(f"Limpios:      {contadores['Limpio']}")

    click.echo()
    if metadata.lista_69b_updated_at:
        click.echo(f"  Listas 69-B actualizadas: {metadata.lista_69b_updated_at}")
    if metadata.lista_69_updated_at:
        click.echo(f"  Listas 69 actualizadas:   {metadata.lista_69_updated_at}")

    # Detalle de los problemáticos
    problemas = [m for m in matches if clasificar(m) in ("EFOS", "Aclarado", "69")]
    if problemas:
        click.echo()
        click.echo("  Detalle:")
        click.echo(f"  {'RFC':<14} {'Etiqueta':<10} {'Detalle'}")
        click.echo(f"  {'─'*14} {'─'*10} {'─'*40}")
        for m in problemas:
            etiqueta = clasificar(m)
            color = {"EFOS": "red", "Aclarado": "yellow", "69": "yellow"}.get(etiqueta, "white")
            detalle = m.situacion_69b or (", ".join(m.supuestos_69) if m.supuestos_69 else "—")
            click.echo(
                f"  {m.rfc:<14} {click.style(etiqueta, fg=color):<21} {detalle}"
            )

    if salida:
        _exportar_csv(matches, salida)
        click.echo()
        print_success(f"Resultados exportados a: {salida}")

    click.echo()


def _recopilar_rfcs(
    rfc_unico: str | None,
    archivo: str | None,
    desde_procesador: bool,
    force_refresh: bool,
) -> list[str]:
    """Recopila los RFCs según el modo elegido. Exclusivo entre sí."""
    modos = sum(bool(x) for x in (rfc_unico, archivo, desde_procesador))
    if modos == 0:
        raise click.UsageError(
            "Debes pasar uno de: --rfc, --archivo o --desde-procesador."
        )
    if modos > 1:
        raise click.UsageError(
            "--rfc, --archivo y --desde-procesador son exclusivos entre sí."
        )

    if rfc_unico:
        return [rfc_unico.strip().upper()]

    if archivo:
        with open(archivo, "r", encoding="utf-8") as f:
            contenido = f.read()
        return [r.strip().upper() for r in _RFC_SPLIT.split(contenido) if r.strip()]

    # desde-procesador
    from ..procesador import abrir_db
    db = abrir_db()
    return db.rfcs_sin_validar_listas(force_refresh=force_refresh)


def _exportar_csv(matches, salida: str) -> None:
    with open(salida, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "RFC", "EnLista69B", "Situacion69B", "FechaPublicacion69B",
            "EnLista69", "Supuestos69", "RiskLevel", "Error",
        ])
        for m in matches:
            writer.writerow([
                m.rfc,
                "Si" if m.en_lista_69b else "No",
                m.situacion_69b or "",
                m.fecha_publicacion_69b or "",
                "Si" if m.en_lista_69 else "No",
                "|".join(m.supuestos_69),
                m.risk_level,
                m.error or "",
            ])
