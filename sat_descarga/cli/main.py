"""Punto de entrada del CLI: grupo principal con subcomandos."""

import logging
import click


@click.group()
@click.option("--debug", is_flag=True, help="Mostrar logs de debug")
def cli(debug):
    """SAT Descarga Masiva — CLI multi-empresa."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
    )


# Importar y registrar subcomandos
from .empresas import empresas
from .descargar import descargar, retomar
from .validar import validar
from .metadata_cmd import metadata
from .organizar import organizar_group

cli.add_command(empresas)
cli.add_command(descargar)
cli.add_command(retomar)
cli.add_command(validar)
cli.add_command(metadata)
cli.add_command(organizar_group)
