"""
CLI: sat-dm organizar/renombrar/deduplicar — Herramientas de organización de XML.
"""

import click

from .display import print_header, print_success, print_warning, print_error


@click.group("organizar")
def organizar_group():
    """Herramientas para organizar archivos XML de CFDIs."""
    pass


@organizar_group.command("carpetas")
@click.argument("origen", type=click.Path(exists=True))
@click.option("--destino", "-d", required=True, type=click.Path(), help="Directorio destino")
@click.option(
    "--estructura", "-e",
    default="rfc_emisor/anio/mes",
    help=(
        "Niveles de carpetas separados por '/' combinando: anio, mes, dia, "
        "rfc, rfc_emisor, rfc_receptor, tipo, flujo — o 'plano'. "
        "Ej: rfc/anio/mes/flujo/tipo"
    ),
)
@click.option(
    "--rfc",
    default=None,
    help="RFC de la empresa; requerido si la estructura usa 'rfc' o 'flujo'",
)
@click.option("--copiar", is_flag=True, help="Copiar en lugar de mover")
def organizar_carpetas(origen, destino, estructura, rfc, copiar):
    """Organiza XMLs en carpetas basándose en su contenido."""
    from sat_descarga.utils.organizador import organizar

    print_header("Organizador de XML en carpetas")

    click.echo(f"  Origen: {origen}")
    click.echo(f"  Destino: {destino}")
    click.echo(f"  Estructura: {estructura}")
    if rfc:
        click.echo(f"  RFC empresa: {rfc}")
    click.echo(f"  Modo: {'copiar' if copiar else 'mover'}")
    click.echo()

    try:
        result = organizar(origen, destino, estructura, copiar, rfc=rfc)
    except ValueError as e:
        print_error(str(e))
        return

    print_success(f"Procesados: {result.archivos_procesados}")
    print_success(f"{'Copiados' if copiar else 'Movidos'}: {result.archivos_movidos}")
    if result.archivos_omitidos:
        print_warning(f"Omitidos: {result.archivos_omitidos}")
    if result.errores:
        print_error(f"Errores: {len(result.errores)}")
        for e in result.errores[:5]:
            click.echo(f"    {e}")
    click.echo()


@organizar_group.command("renombrar")
@click.argument("directorio", type=click.Path(exists=True))
@click.option(
    "--patron", "-p",
    default="emisor_fecha_total",
    help="Patrón de nombre (emisor_fecha_total, uuid, fecha_uuid, etc.)",
)
def renombrar_cmd(directorio, patron):
    """Renombra masivamente XMLs basándose en su contenido."""
    from sat_descarga.utils.organizador import renombrar, PATRONES_NOMBRE

    print_header("Renombrado masivo de XML")

    if patron not in PATRONES_NOMBRE:
        print_error(f"Patrón '{patron}' no válido.")
        click.echo(f"  Opciones: {', '.join(PATRONES_NOMBRE.keys())}")
        return

    click.echo(f"  Directorio: {directorio}")
    click.echo(f"  Patrón: {patron}")
    click.echo()

    result = renombrar(directorio, patron)

    print_success(f"Procesados: {result.archivos_procesados}")
    print_success(f"Renombrados: {result.archivos_movidos}")
    if result.archivos_omitidos:
        print_warning(f"Sin cambio: {result.archivos_omitidos}")
    click.echo()


@organizar_group.command("deduplicar")
@click.argument("directorio", type=click.Path(exists=True))
@click.option("--dry-run", is_flag=True, help="Solo reportar, no eliminar")
def deduplicar_cmd(directorio, dry_run):
    """Elimina archivos XML duplicados (por UUID)."""
    from sat_descarga.utils.organizador import eliminar_duplicados

    print_header("Eliminación de duplicados")

    click.echo(f"  Directorio: {directorio}")
    if dry_run:
        click.echo("  Modo: dry-run (no se eliminará nada)")
    click.echo()

    result = eliminar_duplicados(directorio, dry_run=dry_run)

    print_success(f"Analizados: {result.archivos_analizados}")
    if result.duplicados_encontrados:
        print_warning(f"Duplicados encontrados: {result.duplicados_encontrados}")
        if not dry_run:
            print_success(f"Duplicados eliminados: {result.duplicados_eliminados}")
    else:
        print_success("No se encontraron duplicados.")
    click.echo()
