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

cli.add_command(empresas)
cli.add_command(descargar)
cli.add_command(retomar)
