"""
CLI: sat-dm validar — Validación masiva de estatus CFDI ante el SAT.

Acepta un directorio con XMLs o un archivo CSV/TXT con UUIDs.
No requiere FIEL — usa el endpoint público del SAT.
"""

import click
import os
import csv
from datetime import datetime

from .display import print_header, print_success, print_warning, print_error


@click.command("validar")
@click.argument("origen", type=click.Path(exists=True))
@click.option("--concurrencia", "-c", default=10, help="Hilos paralelos (default 10)")
@click.option(
    "--salida", "-o",
    type=click.Path(),
    default=None,
    help="Archivo CSV de salida con resultados (opcional)",
)
def validar(origen, concurrencia, salida):
    """
    Valida el estatus de CFDIs ante el SAT (Vigente/Cancelado).

    ORIGEN puede ser:
    - Un directorio con archivos XML
    - Un archivo XML individual

    No requiere e-firma — usa el servicio público del SAT.
    """
    from sat_descarga.validacion import validar_masivo

    print_header("Validación de CFDI ante el SAT")

    # Recopilar CFDIs a validar
    cfdis = _recopilar_cfdis(origen)

    if not cfdis:
        print_warning("No se encontraron CFDIs para validar.")
        return

    click.echo(f"  CFDIs a validar: {len(cfdis)}")
    click.echo(f"  Concurrencia: {concurrencia} hilos")
    click.echo()

    # Validar con barra de progreso
    with click.progressbar(
        length=len(cfdis),
        label="  Validando",
        show_pos=True,
    ) as bar:
        # Usamos validar_masivo pero actualizamos progreso
        resultados = validar_masivo(cfdis, concurrency=concurrencia)
        bar.update(len(cfdis))

    # Mostrar resumen
    click.echo()
    vigentes = sum(1 for r in resultados if r.estado == "Vigente")
    cancelados = sum(1 for r in resultados if r.estado == "Cancelado")
    no_encontrados = sum(1 for r in resultados if r.estado == "No Encontrado")
    errores = sum(1 for r in resultados if r.estado == "Error")

    print_success(f"Vigentes:       {vigentes}")
    if cancelados > 0:
        print_error(f"Cancelados:     {cancelados}")
    else:
        click.echo(f"  Cancelados:     {cancelados}")
    if no_encontrados > 0:
        print_warning(f"No Encontrados: {no_encontrados}")
    else:
        click.echo(f"  No Encontrados: {no_encontrados}")
    if errores > 0:
        print_warning(f"Errores:        {errores}")

    # Mostrar cancelados y no encontrados en detalle
    problema = [r for r in resultados if r.estado in ("Cancelado", "No Encontrado")]
    if problema:
        click.echo()
        click.echo("  Detalle de cancelados/no encontrados:")
        click.echo(f"  {'UUID':<38} {'Estado':<16} {'Cancelable'}")
        click.echo(f"  {'─'*38} {'─'*16} {'─'*20}")
        for r in problema:
            estado_color = "red" if r.estado == "Cancelado" else "yellow"
            click.echo(
                f"  {r.uuid:<38} "
                f"{click.style(r.estado, fg=estado_color):<27} "
                f"{r.es_cancelable or '—'}"
            )

    # Exportar a CSV si se pidió
    if salida:
        _exportar_csv(resultados, salida)
        click.echo()
        print_success(f"Resultados exportados a: {salida}")

    click.echo()


def _recopilar_cfdis(origen: str) -> list[dict]:
    """Lee XMLs del origen y extrae los datos necesarios para validar."""
    from sat_descarga.xml_reader import leer_cfdi, leer_directorio

    cfdis = []

    if os.path.isfile(origen):
        # Archivo XML individual
        if origen.lower().endswith(".xml"):
            try:
                header = leer_cfdi(origen)
                cfdis.append({
                    "uuid": header.uuid,
                    "emisor_rfc": header.emisor_rfc,
                    "receptor_rfc": header.receptor_rfc,
                    "total": header.total,
                })
            except (ValueError, Exception) as e:
                print_warning(f"No se pudo leer {origen}: {e}")
    elif os.path.isdir(origen):
        # Directorio con XMLs
        headers = leer_directorio(origen)
        for h in headers:
            if h.uuid:
                cfdis.append({
                    "uuid": h.uuid,
                    "emisor_rfc": h.emisor_rfc,
                    "receptor_rfc": h.receptor_rfc,
                    "total": h.total,
                })

    return cfdis


def _exportar_csv(resultados, salida: str):
    """Exporta resultados de validación a CSV."""
    with open(salida, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "UUID", "Estado", "EsCancelable",
            "EstatusCancelacion", "ValidacionEFOS", "Error",
        ])
        for r in resultados:
            writer.writerow([
                r.uuid, r.estado, r.es_cancelable or "",
                r.estatus_cancelacion or "", r.validacion_efos or "",
                r.error or "",
            ])
