"""
Subcomandos del CLI para generar solicitudes de e.firma y CSD (equivalente a la
app "Certifica" del SAT):

    sat-dm generar fiel   --rfc ... --curp ... --correo ...   → .req + .key
    sat-dm renovar fiel   --cer ... --key ...                 → .ren + .key
    sat-dm solicitar csd  --cer ... --key ... --sucursal ...  → .sdg + .key

La generación es 100% local. El ENVÍO se hace aparte en CertiSAT Web
(https://www.sat.gob.mx → e.firma → "Renovación del certificado" / envío de CSD).
"""

import click

from .display import print_header, print_success, print_warning
from sat_descarga.certifica import (
    generar_requerimiento_fiel,
    generar_renovacion_fiel,
    generar_renovacion_fiel_moral,
    generar_solicitud_csd,
)


def _cargar_fiel(cer, key, password):
    from sat_descarga.core.fiel import FIEL

    if not password:
        password = click.prompt("Contraseña de la clave privada vigente", hide_input=True)
    return FIEL(cer, key, password)


def _nueva_password(nueva):
    if nueva:
        return nueva
    return click.prompt(
        "Contraseña para la NUEVA clave privada",
        hide_input=True,
        confirmation_prompt=True,
    )


def _reportar(res: dict, siguiente: str):
    for etiqueta, ruta in res.items():
        print_success(f"{etiqueta.upper()}: {ruta}")
    print_warning(siguiente)


# ---------------------------------------------------------------------------
# generar fiel  (e.firma nueva, sin e.firma previa)
# ---------------------------------------------------------------------------

@click.group()
def generar():
    """Genera archivos de solicitud de e.firma nueva (.req)."""


@generar.command("fiel")
@click.option("--rfc", required=True, help="RFC del contribuyente")
@click.option("--curp", default="", help="CURP (persona física)")
@click.option("--correo", required=True, help="Correo electrónico")
@click.option("--nueva-password", default=None, help="Contraseña de la nueva clave privada")
@click.option("--salida", default=None, help="Directorio de salida (default: actual)")
def generar_fiel_cmd(rfc, curp, correo, nueva_password, salida):
    """Requerimiento de Generación de e.firma (.req + .key nuevos)."""
    print_header("Generación de e.firma (.req)")
    res = generar_requerimiento_fiel(rfc, curp, correo, _nueva_password(nueva_password), salida)
    _reportar(res, "Envía el .req en CertiSAT Web (requiere cita/registro de e.firma en el SAT).")


# ---------------------------------------------------------------------------
# renovar fiel  (renovación con la e.firma vigente)
# ---------------------------------------------------------------------------

@click.group()
def renovar():
    """Renueva la e.firma vigente (genera el .ren para CertiSAT Web)."""


@renovar.command("fiel")
@click.option("--cer", type=click.Path(exists=True), required=True, help="Archivo .cer VIGENTE")
@click.option("--key", type=click.Path(exists=True), required=True, help="Archivo .key VIGENTE")
@click.option("--password", default=None, help="Contraseña de la clave privada vigente (se pide oculta si falta)")
@click.option("--correo", default=None, help="Correo para el nuevo requerimiento (default: el del cert)")
@click.option("--rfc-moral", default=None, help="RFC de la persona moral (renovación PM con representante legal)")
@click.option("--nueva-password", default=None, help="Contraseña de la nueva clave privada")
@click.option("--salida", default=None, help="Directorio de salida (default: actual)")
def renovar_fiel_cmd(cer, key, password, correo, rfc_moral, nueva_password, salida):
    """Requerimiento de Renovación de e.firma (.ren + .key nuevos)."""
    print_header("Renovación de e.firma (.ren)")
    fiel = _cargar_fiel(cer, key, password)
    if not fiel.vigente:
        print_warning("El certificado ya está vencido; el SAT solo permite renovar antes de vencer.")
    nueva = _nueva_password(nueva_password)
    if rfc_moral:
        res = generar_renovacion_fiel_moral(fiel, rfc_moral, correo or "", nueva, salida)
    else:
        res = generar_renovacion_fiel(fiel, correo, nueva, salida)
    _reportar(res, "Sube el .ren en CertiSAT Web → «Renovación del certificado» (login con la e.firma vigente).")


# ---------------------------------------------------------------------------
# solicitar csd  (certificado de sello digital)
# ---------------------------------------------------------------------------

@click.group()
def solicitar():
    """Solicita certificados del SAT (CSD)."""


@solicitar.command("csd")
@click.option("--cer", type=click.Path(exists=True), required=True, help="Archivo .cer de la e.firma")
@click.option("--key", type=click.Path(exists=True), required=True, help="Archivo .key de la e.firma")
@click.option("--password", default=None, help="Contraseña de la clave privada (se pide oculta si falta)")
@click.option("--sucursal", required=True, help="Nombre de la sucursal/unidad (va en el OU del CSD)")
@click.option("--nueva-password", default=None, help="Contraseña de la nueva clave privada del sello")
@click.option("--salida", default=None, help="Directorio de salida (default: actual)")
def solicitar_csd_cmd(cer, key, password, sucursal, nueva_password, salida):
    """Solicitud de Certificado de Sello Digital (.sdg + .key nuevos)."""
    print_header("Solicitud de CSD (.sdg)")
    fiel = _cargar_fiel(cer, key, password)
    res = generar_solicitud_csd(fiel, sucursal, _nueva_password(nueva_password), salida)
    _reportar(res, "Sube el .sdg en CertiSAT Web → envío de solicitud de Certificados de Sello Digital.")
