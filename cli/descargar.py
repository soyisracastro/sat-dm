"""Comandos de descarga: flujo principal y retomar solicitudes."""

import click
from datetime import date, datetime

from . import config_store
from .empresas import _seleccionar_empresa
from .display import print_header, print_success, print_warning, print_error

from sat_descarga import descargar_cfdi, verificar_solicitud_existente


TIPOS = {"E": "Emitidos", "R": "Recibidos"}
ESTADOS = {"V": "Vigente", "C": "Cancelado", "T": "Todos"}


def _parse_fecha(text: str) -> date:
    return datetime.strptime(text, "%Y-%m-%d").date()


def _prompt_rfc(rfc: str | None) -> str | None:
    """Resuelve RFC: usa el dado, el default, o pide interactivamente."""
    if rfc:
        return rfc
    default = config_store.get_default()
    empresas = config_store.list_empresas()
    if not empresas:
        print_error("No hay empresas registradas. Usa 'sat-dm empresas add'.")
        return None
    if len(empresas) == 1:
        return empresas[0]["rfc"]
    return _seleccionar_empresa("Selecciona empresa")


def _prompt_fechas(desde: str | None, hasta: str | None) -> tuple[date, date]:
    """Resuelve fechas: usa las dadas o pide interactivamente."""
    hoy = date.today()
    default_desde = f"{hoy.year}-01-01"
    default_hasta = hoy.strftime("%Y-%m-%d")

    if desde is None:
        desde = click.prompt("  Fecha inicio", default=default_desde)
    if hasta is None:
        hasta = click.prompt("  Fecha fin", default=default_hasta)

    return _parse_fecha(desde), _parse_fecha(hasta)


def _prompt_tipo(tipo: str | None) -> list[str]:
    """Resuelve tipo. Retorna lista de tipos a descargar."""
    if tipo is None:
        tipo = click.prompt(
            "  Tipo: (E)mitidos / (R)ecibidos / (A)mbos",
            default="A",
        )
    tipo = tipo.upper()
    if tipo == "A":
        return ["E", "R"]
    if tipo in ("E", "R"):
        return [tipo]
    print_error(f"Tipo inválido: {tipo}. Usa E, R o A.")
    raise click.Abort()


def _prompt_estado(estado: str | None) -> str:
    """Resuelve estado del comprobante."""
    if estado is None:
        estado = click.prompt(
            "  Estado: (V)igente / (C)ancelado / (T)odos",
            default="V",
        )
    estado = estado.upper()
    if estado in ESTADOS:
        return ESTADOS[estado]
    print_error(f"Estado inválido: {estado}. Usa V, C o T.")
    raise click.Abort()


def _ejecutar_descarga(
    empresa: dict,
    fecha_inicio: date,
    fecha_fin: date,
    tipo_comprobante: str,
    estado_comprobante: str,
    salida: str,
):
    """Ejecuta una descarga individual (emitidos o recibidos)."""
    rfc = empresa["rfc"]
    label = TIPOS[tipo_comprobante]
    directorio = f"{salida}/{rfc}/{label.lower()}/"

    print_header(f"{label} — {rfc} ({fecha_inicio} a {fecha_fin})")

    try:
        zips = descargar_cfdi(
            cer_path=empresa["cer_path"],
            key_path=empresa["key_path"],
            password=empresa["password"],
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            tipo_solicitud="CFDI",
            tipo_comprobante=tipo_comprobante,
            estado_comprobante=estado_comprobante,
            directorio_salida=directorio,
            extraer=True,
        )

        if zips:
            print_success(f"{label}: {len(zips)} paquete(s) descargados en {directorio}")
            for z in zips:
                click.echo(f"    -> {z}")
        else:
            print_warning(f"{label}: Sin paquetes para descargar.")

        return True

    except RuntimeError as e:
        msg = str(e)
        if "5002" in msg or "agotado" in msg.lower():
            print_error(f"{label}: Solicitudes agotadas para este rango de fechas.")
            print_warning("Intenta de nuevo mas tarde o ajusta el rango.")
        else:
            print_error(f"{label}: {msg}")
        return False


@click.command()
@click.option("--rfc", default=None, help="RFC de la empresa")
@click.option("--desde", default=None, help="Fecha inicio (YYYY-MM-DD)")
@click.option("--hasta", default=None, help="Fecha fin (YYYY-MM-DD)")
@click.option("--tipo", default=None, help="E=emitidos, R=recibidos, A=ambos")
@click.option("--estado", default=None, help="V=vigente, C=cancelado, T=todos")
@click.option("--salida", default="./descargas", help="Directorio base de salida")
def descargar(rfc, desde, hasta, tipo, estado, salida):
    """Descargar CFDIs del SAT (interactivo o con argumentos)."""
    rfc = _prompt_rfc(rfc)
    if rfc is None:
        return

    try:
        empresa = config_store.get_empresa(rfc)
    except KeyError:
        print_error(f"Empresa {rfc} no registrada. Usa 'sat-dm empresas add'.")
        return

    print_header(f"Descarga Masiva — {empresa['nombre']} ({rfc})")

    fecha_inicio, fecha_fin = _prompt_fechas(desde, hasta)
    tipos = _prompt_tipo(tipo)
    estado_comprobante = _prompt_estado(estado)

    for t in tipos:
        _ejecutar_descarga(empresa, fecha_inicio, fecha_fin, t, estado_comprobante, salida)


@click.command()
@click.argument("id_solicitud")
@click.option("--rfc", default=None, help="RFC de la empresa")
@click.option("--salida", default="./descargas", help="Directorio base de salida")
def retomar(id_solicitud, rfc, salida):
    """Retomar una solicitud previa por RequestID."""
    rfc = _prompt_rfc(rfc)
    if rfc is None:
        return

    try:
        empresa = config_store.get_empresa(rfc)
    except KeyError:
        print_error(f"Empresa {rfc} no registrada.")
        return

    print_header(f"Retomando solicitud {id_solicitud}")

    directorio = f"{salida}/{rfc}/"

    try:
        zips = verificar_solicitud_existente(
            cer_path=empresa["cer_path"],
            key_path=empresa["key_path"],
            password=empresa["password"],
            id_solicitud=id_solicitud,
            directorio_salida=directorio,
            extraer=True,
            poll=True,
        )

        if zips:
            print_success(f"Descargados {len(zips)} paquete(s) en {directorio}")
            for z in zips:
                click.echo(f"    -> {z}")
        else:
            print_warning("Solicitud aun no lista.")

    except RuntimeError as e:
        print_error(f"Error: {e}")
