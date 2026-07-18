"""Subcomando `sat-dm diot`: genera el TXT de carga masiva de la DIOT 2025.

Prellena desde el buffer del procesador (los XMLs se cargan antes con la app
o contra el mismo buffer), valida contra el instructivo del SAT y escribe el
archivo. Layout y reglas: docs/producto/diot-2025.md.
"""

from pathlib import Path

import click

from .config_store import get_descargas_dir
from .display import print_error, print_header, print_success, print_warning


@click.command()
@click.option("--rfc", required=True, help="RFC de la empresa (dueña del buffer)")
@click.option("--periodo", required=True, help="Periodo a declarar (YYYY-MM)")
@click.option(
    "--salida",
    type=click.Path(dir_okay=False, writable=True),
    default=None,
    help="Ruta del TXT (default: {descargas}/{RFC}_diot_{periodo}.txt)",
)
@click.option(
    "--forzar",
    is_flag=True,
    help="Exporta aunque haya advertencias (los errores siempre bloquean)",
)
def diot(rfc: str, periodo: str, salida: str | None, forzar: bool):
    """Genera el archivo .txt de carga masiva de la DIOT (ejercicios 2025+)."""
    from ..diot import (
        DiotInvalida,
        exportar_txt,
        nombre_archivo,
        prellenar_y_guardar,
        validar_filas,
    )

    print_header(f"DIOT {periodo} — {rfc.upper()}")

    try:
        estado = prellenar_y_guardar(rfc, periodo)
    except ValueError as e:
        print_error(str(e))
        raise SystemExit(1)

    resumen = estado.get("resumen", {})
    filas = estado.get("filas", [])
    click.echo(
        f"  CFDIs considerados: {resumen.get('cfdis_considerados', 0)} · "
        f"proveedores: {len(filas)}"
    )
    if resumen.get("cfdis_sin_desglose"):
        print_warning(
            f"{resumen['cfdis_sin_desglose']} CFDIs se cargaron con una versión "
            "anterior: la base 16% se estimó desde el IVA. Recarga los XMLs para "
            "el desglose exacto."
        )
    if not filas:
        print_error("No hay CFDIs recibidos en el buffer para ese periodo.")
        click.echo(
            "  Carga los XMLs primero (pantalla Comprobantes de la app, o "
            "POST /procesador/cfdi/cargar) y vuelve a intentar."
        )
        raise SystemExit(1)

    validacion = validar_filas(filas)
    for adv in validacion["advertencias"]:
        print_warning(adv["mensaje"])
    if validacion["advertencias"] and not forzar:
        click.echo("  (usa --forzar para exportar con advertencias)")
        raise SystemExit(1)

    try:
        data = exportar_txt(filas)
    except DiotInvalida as e:
        for err in e.errores:
            print_error(err["mensaje"])
        raise SystemExit(1)

    destino = (
        Path(salida)
        if salida
        # Nunca el cwd: en Windows empacado es de solo lectura.
        else Path(get_descargas_dir()) / nombre_archivo(rfc, periodo)
    )
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(data)
    print_success(f"DIOT generada: {destino}")
    click.echo("  Verifica el archivo subiéndolo a la aplicación DIOT del SAT.")
