"""
CLI: sat-dm metadata — Descarga y parseo de metadata de CFDIs.

La metadata es un resumen rápido (UUID, RFC, monto, estatus) que el SAT
procesa en segundos/minutos (vs 24-72 hrs para CFDIs completos).
Útil para contar/auditar CFDIs antes de hacer la descarga completa.
"""

import csv
import click
from datetime import date

from .display import print_header, print_success, print_warning, print_error
from . import config_store


@click.command("metadata")
@click.option("--rfc", default=None, help="RFC de la empresa (usa default si no se especifica)")
@click.option("--desde", required=True, type=click.DateTime(formats=["%Y-%m-%d"]), help="Fecha inicio (YYYY-MM-DD)")
@click.option("--hasta", required=True, type=click.DateTime(formats=["%Y-%m-%d"]), help="Fecha fin (YYYY-MM-DD)")
@click.option(
    "--tipo", "-t",
    type=click.Choice(["E", "R"], case_sensitive=False),
    default="E",
    help="Emitidos (E) o Recibidos (R)",
)
@click.option("--salida", "-o", default="./metadata/", help="Directorio de salida")
@click.option("--csv-export", "csv_path", default=None, help="Exportar resultados a CSV (default: ./metadata/reporte.csv)")
@click.option("--local", is_flag=True, help="Solo parsear metadata ya descargada (no contactar SAT)")
def metadata(rfc, desde, hasta, tipo, salida, csv_path, local):
    """
    Descarga metadata de CFDIs del SAT (resumen rápido).

    Mucho más rápido que la descarga completa. Retorna UUID, RFC,
    monto y estatus de cada CFDI sin descargar los XMLs.

    Usa --local para re-procesar metadata ya descargada sin contactar al SAT.
    """
    from sat_descarga.metadata import extraer_metadata_de_directorio

    print_header("Descarga de Metadata del SAT")

    if local:
        # Solo parsear lo que ya está descargado
        click.echo(f"  Parseando metadata local en: {salida}")
        click.echo()
        records = extraer_metadata_de_directorio(salida)
    else:
        from sat_descarga.client import descargar_metadata

        try:
            if rfc:
                empresa = config_store.get_empresa(rfc)
            else:
                default_rfc = config_store.get_default()
                if not default_rfc:
                    print_error("No hay empresa default. Usa 'sat-dm empresas add'.")
                    return
                empresa = config_store.get_empresa(default_rfc)
        except KeyError:
            print_error(f"No se encontró la empresa con RFC {rfc or 'default'}")
            return

        click.echo(f"  RFC: {empresa['rfc']}")
        click.echo(f"  Periodo: {desde.strftime('%Y-%m-%d')} a {hasta.strftime('%Y-%m-%d')}")
        click.echo(f"  Tipo: {'Emitidos' if tipo.upper() == 'E' else 'Recibidos'}")
        click.echo()

        try:
            records = descargar_metadata(
                cer_path=empresa["cer_path"],
                key_path=empresa["key_path"],
                password=empresa["password"],
                fecha_inicio=desde.date() if hasattr(desde, 'date') else desde,
                fecha_fin=hasta.date() if hasattr(hasta, 'date') else hasta,
                directorio_salida=salida,
                tipo_comprobante=tipo.upper(),
            )
        except Exception as e:
            print_error(f"Error: {e}")
            return

    if not records:
        print_warning("No se encontró metadata para el periodo.")
        return

    # Resumen
    vigentes = sum(1 for r in records if r.estatus.lower() in ("vigente", "1"))
    cancelados = sum(1 for r in records if r.estatus.lower() in ("cancelado", "0"))
    total_monto = sum(float(r.monto or 0) for r in records)

    print_success(f"Total registros: {len(records)}")
    click.echo(f"  Vigentes:   {vigentes}")
    click.echo(f"  Cancelados: {cancelados}")
    click.echo(f"  Monto total: ${total_monto:,.2f}")

    # Exportar a CSV si se pidió
    if csv_path:
        # Si es solo un nombre de archivo sin ruta, ponerlo en ./metadata/
        import os
        if os.path.dirname(csv_path) == "":
            csv_path = os.path.join(salida, csv_path)
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        _exportar_csv(records, csv_path)
        click.echo()
        print_success(f"Exportado a: {csv_path}")

    click.echo()


def _exportar_csv(records, path: str):
    """Exporta metadata a CSV."""
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "UUID", "RFC Emisor", "Nombre Emisor", "RFC Receptor",
            "Nombre Receptor", "Fecha Emisión", "Monto",
            "Efecto", "Estatus", "Fecha Cancelación",
        ])
        for r in records:
            writer.writerow([
                r.uuid, r.rfc_emisor, r.nombre_emisor, r.rfc_receptor,
                r.nombre_receptor, r.fecha_emision, r.monto,
                r.efecto_comprobante, r.estatus, r.fecha_cancelacion,
            ])
