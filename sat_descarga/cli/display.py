"""Helpers de formato para terminal."""

import click


def print_header(text: str):
    width = max(len(text) + 4, 50)
    click.echo()
    click.echo("=" * width)
    click.echo(f"  {text}")
    click.echo("=" * width)
    click.echo()


def print_success(text: str):
    click.echo(click.style(f"  {text}", fg="green"))


def print_warning(text: str):
    click.echo(click.style(f"  {text}", fg="yellow"))


def print_error(text: str):
    click.echo(click.style(f"  {text}", fg="red"))


def print_tabla_empresas(empresas: list[dict]):
    from datetime import date

    if not empresas:
        print_warning("No hay empresas registradas. Usa 'sat-dm empresas add'.")
        return

    click.echo(f"  {'#':<4} {'RFC':<16} {'Nombre':<30} {'Vence':<14} {'Default'}")
    click.echo(f"  {'─'*4} {'─'*16} {'─'*30} {'─'*14} {'─'*7}")
    for i, emp in enumerate(empresas, 1):
        default = click.style("*", fg="green") if emp["default"] else " "
        venc = emp.get("vencimiento", "")
        if venc:
            try:
                fecha_venc = date.fromisoformat(venc)
                dias = (fecha_venc - date.today()).days
                if dias < 0:
                    venc_str = click.style(f"{venc} VENCIDA", fg="red")
                elif dias <= 90:
                    venc_str = click.style(f"{venc} ({dias}d)", fg="yellow")
                else:
                    venc_str = click.style(venc, fg="green")
            except ValueError:
                venc_str = venc
        else:
            venc_str = "—"
        click.echo(f"  {i:<4} {emp['rfc']:<16} {emp['nombre']:<30} {venc_str:<25} {default}")
    click.echo()
