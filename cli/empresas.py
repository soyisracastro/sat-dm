"""Comandos para gestionar el catálogo de empresas (FIELs)."""

import click

from . import config_store
from .display import print_header, print_success, print_error, print_warning, print_tabla_empresas


@click.group()
def empresas():
    """Gestionar empresas registradas."""


@empresas.command("add")
@click.option("--nombre", default=None, help="Nombre descriptivo")
@click.option("--cer", default=None, help="Ruta al certificado FIEL (.cer)")
@click.option("--key", default=None, help="Ruta a la llave privada (.key)")
@click.option("--password", default=None, help="Contraseña de la llave privada")
def add(nombre, cer, key, password):
    """Registrar una nueva empresa con su e-firma.

    Si no se dan rutas, busca archivos .cer/.key en el directorio actual.
    """
    if cer is None or key is None:
        cer, key = _detectar_fiel(cer, key)
        if cer is None:
            return

    if password is None:
        # Buscar fiel.txt / password.txt junto al .key
        password = _detectar_password(key)
        if password is None:
            password = click.prompt("  Contraseña de la llave privada", hide_input=True)

    if nombre is None:
        nombre = click.prompt("  Nombre de la empresa")

    try:
        rfc = config_store.add_empresa(nombre, cer, key, password)
        print_success(f"Empresa registrada: {rfc} — {nombre}")
        print_success(f"Archivos copiados a ./efirma/{rfc}/")
    except FileNotFoundError as e:
        print_error(f"Archivo no encontrado: {e}")
    except Exception as e:
        print_error(f"Error al cargar la e-firma: {e}")


def _detectar_fiel(cer: str | None, key: str | None) -> tuple[str | None, str | None]:
    """Busca archivos .cer y .key. Ignora los ya organizados en efirma/{RFC}/."""
    from pathlib import Path

    empresas_existentes = {e["rfc"] for e in config_store.list_empresas()}

    # Directorios que no contienen FIELs de usuario
    _EXCLUDE_DIRS = {"tests", ".venv", "__pycache__", ".git", ".pytest_cache", "node_modules"}

    def _buscar(extension: str) -> list[Path]:
        """Busca archivos con la extensión dada, excluyendo tests, .venv, CSD y ya registrados."""
        encontrados = list(Path(".").glob(f"**/*{extension}"))
        return [
            p for p in encontrados
            if not (p.parent.name in empresas_existentes and p.parent.parent.name == "efirma")
            and not any(part in _EXCLUDE_DIRS for part in p.parts)
            and not any(part.startswith("CSD") for part in p.parts)  # Excluir CSD (sello digital)
            and "CSD" not in p.name.upper()  # Excluir archivos con CSD en el nombre
        ]

    def _elegir(archivos: list[Path], label: str) -> str | None:
        if len(archivos) == 1:
            click.echo(f"  {label} detectado: {archivos[0]}")
            return str(archivos[0])
        elif len(archivos) > 1:
            click.echo(f"  Archivos {label} encontrados:")
            for i, f in enumerate(archivos, 1):
                click.echo(f"    {i}. {f}")
            choice = click.prompt("  Selecciona", type=int, default=1)
            if 1 <= choice <= len(archivos):
                return str(archivos[choice - 1])
            print_error("Selección inválida.")
            return None
        else:
            return click.prompt(f"  Ruta al archivo {label.lower()}")

    if cer is None:
        cer = _elegir(_buscar(".cer"), "Certificado")
        if cer is None:
            return None, None

    if key is None:
        key = _elegir(_buscar(".key"), "Llave")
        if key is None:
            return None, None

    return cer, key


def _detectar_password(key_path: str) -> str | None:
    """Busca fiel.txt o password.txt junto al archivo .key."""
    from pathlib import Path
    key_dir = Path(key_path).parent
    for name in ("fiel.txt", "password.txt"):
        pwd_file = key_dir / name
        if pwd_file.exists():
            password = pwd_file.read_text().strip()
            if password:
                click.echo(f"  Contraseña detectada en {pwd_file}")
                return password
    return None


@empresas.command("list")
def list_cmd():
    """Listar empresas registradas."""
    empresas_list = config_store.list_empresas()
    print_header("Empresas registradas")
    print_tabla_empresas(empresas_list)


@empresas.command("remove")
@click.option("--rfc", default=None, help="RFC de la empresa a eliminar")
def remove(rfc):
    """Eliminar una empresa del catálogo."""
    if rfc is None:
        rfc = _seleccionar_empresa("Selecciona empresa a eliminar")
        if rfc is None:
            return

    empresa = config_store.get_empresa(rfc)
    if not click.confirm(f"  Eliminar {rfc} — {empresa['nombre']}?"):
        return

    config_store.remove_empresa(rfc)
    print_success(f"Empresa {rfc} eliminada.")


@empresas.command("default")
@click.option("--rfc", default=None, help="RFC a marcar como default")
def set_default(rfc):
    """Marcar una empresa como la predeterminada."""
    if rfc is None:
        rfc = _seleccionar_empresa("Selecciona empresa default")
        if rfc is None:
            return

    try:
        config_store.set_default(rfc)
        print_success(f"Empresa default: {rfc}")
    except KeyError:
        print_error(f"No se encontró empresa con RFC {rfc}")


def _seleccionar_empresa(prompt_text: str = "Selecciona empresa") -> str | None:
    """Muestra lista numerada y pide selección. Retorna RFC o None."""
    empresas_list = config_store.list_empresas()
    if not empresas_list:
        print_warning("No hay empresas registradas. Usa 'sat-dm empresas add'.")
        return None

    click.echo(f"\n  {prompt_text}:")
    for i, emp in enumerate(empresas_list, 1):
        default = " *" if emp["default"] else ""
        click.echo(f"    {i}. {emp['rfc']} — {emp['nombre']}{default}")

    while True:
        choice = click.prompt("  >", type=int, default=1)
        if 1 <= choice <= len(empresas_list):
            return empresas_list[choice - 1]["rfc"]
        click.echo(f"  Opción inválida. Elige entre 1 y {len(empresas_list)}.")
