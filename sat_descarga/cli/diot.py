"""Subcomandos `sat-dm diot`: generar el TXT de carga masiva y presentarlo.

- `sat-dm diot generar`   — genera el TXT desde el buffer del procesador
  (layout y reglas: docs/producto/diot-2025.md). Invocar `sat-dm diot` con
  las opciones directas sigue funcionando como alias (compatibilidad).
- `sat-dm diot presentar` — sube el TXT al portal del SAT con e.firma, valida
  la sección Totales contra el archivo y, solo con --enviar, firma y presenta
  la declaración capturando el acuse PDF.
"""

from pathlib import Path

import click

from .config_store import get_descargas_dir
from .display import print_error, print_header, print_success, print_warning


def _generar(rfc: str, periodo: str, salida: str | None, forzar: bool):
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


@click.group(invoke_without_command=True)
@click.option("--rfc", default=None, help="RFC de la empresa (alias de `generar`)")
@click.option("--periodo", default=None, help="Periodo a declarar (YYYY-MM)")
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
@click.pass_context
def diot(ctx, rfc, periodo, salida, forzar):
    """DIOT 2025: genera el TXT de carga masiva y preséntalo en el SAT."""
    if ctx.invoked_subcommand is not None:
        return
    # Compatibilidad: `sat-dm diot --rfc X --periodo Y` = `sat-dm diot generar`.
    if not rfc or not periodo:
        click.echo(ctx.get_help())
        raise SystemExit(0 if not rfc and not periodo else 1)
    _generar(rfc, periodo, salida, forzar)


@diot.command()
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
def generar(rfc: str, periodo: str, salida: str | None, forzar: bool):
    """Genera el archivo .txt de carga masiva de la DIOT (ejercicios 2025+)."""
    _generar(rfc, periodo, salida, forzar)


@diot.command()
@click.option("--rfc", default=None,
              help="RFC del catálogo (toma la e.firma de `sat-dm empresas`)")
@click.option("--cer", type=click.Path(exists=True), default=None,
              help="Archivo .cer (si no usas el catálogo)")
@click.option("--key", type=click.Path(exists=True), default=None,
              help="Archivo .key (si no usas el catálogo)")
@click.option("--password", default=None,
              help="Contraseña de la clave privada (se pide oculta si falta)")
@click.option("--txt", "txt_path", required=True,
              type=click.Path(exists=True, dir_okay=False),
              help="Archivo .txt de carga masiva a presentar")
@click.option("--ejercicio", required=True, type=int, help="Ejercicio (p. ej. 2025)")
@click.option("--periodo", required=True, help="Mes a declarar (1-12)")
@click.option("--tipo", default="001", show_default=True,
              help="Tipo de declaración (001=Normal, 003=Normal por corrección)")
@click.option("--enviar", is_flag=True,
              help="Firma y PRESENTA la declaración (sin esta bandera solo "
                   "valida la sección Totales y se detiene)")
@click.option("--si", "sin_confirmar", is_flag=True,
              help="Con --enviar: no pedir confirmación interactiva (batch)")
@click.option("--salida", default=None,
              help="Carpeta para acuse y evidencia (default: "
                   "{descargas}/diot/presentaciones/{RFC}/)")
@click.option("--ver-navegador", is_flag=True, default=False,
              help="Debug: mostrar el navegador (headful)")
def presentar(rfc, cer, key, password, txt_path, ejercicio, periodo, tipo,
              enviar, sin_confirmar, salida, ver_navegador):
    """Sube el TXT al portal DIOT del SAT (e.firma, sin captcha) y lo valida.

    ADVERTENCIA: este flujo SOLO aplica a empresas que responden «No» en
    «¿Aplicaste estímulos fiscales?» (se responde automáticamente). Si la
    empresa aplica estímulos fiscales, presenta la declaración a mano.

    Por default NO envía nada: sube el archivo, coteja Totales (operaciones,
    IVA acreditable e IVA retenido) contra el propio TXT y se detiene. El envío
    real requiere --enviar y una confirmación (omitible con --si).
    """
    from ..portal.diot_presentacion import presentar_diot_fiel

    if rfc and not (cer and key):
        from . import config_store
        try:
            empresa = config_store.get_empresa(rfc.strip().upper())
        except KeyError:
            print_error(f"Empresa {rfc} no registrada. Usa 'sat-dm empresas add' "
                        "o pasa --cer/--key/--password.")
            raise SystemExit(1)
        cer = cer or empresa.get("cer_path")
        key = key or empresa.get("key_path")
        password = password or empresa.get("password")
        if not (cer and key):
            print_error(f"La empresa {rfc} no tiene e.firma en el catálogo.")
            raise SystemExit(1)
    if not (cer and key):
        print_error("Falta la e.firma: pasa --rfc (catálogo) o --cer y --key.")
        raise SystemExit(1)
    if not password:
        password = click.prompt("  Contraseña de la clave privada", hide_input=True)

    rfc_etiqueta = (rfc or "").strip().upper()
    destino = salida or str(
        Path(get_descargas_dir()) / "diot" / "presentaciones"
        / (rfc_etiqueta or "sin_rfc") / str(ejercicio)
        / f"{int(periodo):02d}-{ejercicio}"
    )

    print_header(f"DIOT {ejercicio}-{int(periodo):02d} — "
                 f"{rfc_etiqueta or 'e.firma'} "
                 f"({'ENVÍO' if enviar else 'solo validación'})")
    print_warning(
        "Flujo soportado únicamente SIN estímulos fiscales (se responde «No»)."
    )

    def _confirmar(resumen: dict) -> bool:
        click.echo(
            f"\n  Periodo {resumen['ejercicio']}-{resumen['periodo']}: "
            f"{resumen['operaciones']} operaciones · "
            f"IVA acreditable ${resumen['iva_acreditable']:,} · "
            f"IVA retenido ${resumen['iva_retenido']:,}"
        )
        if sin_confirmar:
            return True
        return click.confirm(
            "  ¿Firmar y PRESENTAR la declaración? (irreversible)", default=False
        )

    resultado = presentar_diot_fiel(
        cer_path=cer, key_path=key, password=password, txt_path=txt_path,
        ejercicio=ejercicio, periodo=periodo, tipo_declaracion=tipo,
        directorio_salida=destino, enviar=enviar,
        headless=not ver_navegador, confirmar=_confirmar,
    )

    portal = resultado.get("totales_portal") or {}
    if portal:
        click.echo(
            f"  Portal: {portal['operaciones']} operaciones · "
            f"IVA acreditable ${portal['iva_acreditable']:,} · "
            f"IVA retenido ${portal['iva_retenido']:,}"
        )
    if resultado.get("discrepancias"):
        for d in resultado["discrepancias"]:
            print_error(d)
        print_error("Totales con discrepancias: NO se envió nada.")
        raise SystemExit(1)

    if resultado["estado"] == "presentado":
        if resultado.get("acuse"):
            print_success(f"Declaración presentada. Acuse: {resultado['acuse']}")
        else:
            print_warning(
                "Declaración presentada, pero el acuse no se pudo descargar: "
                "recupéralo con `sat-dm diot acuse` (o en el portal, menú "
                "«Impresión de acuse»)."
            )
    elif resultado["estado"] == "no_presentada":
        print_error("El envío NO se concretó: la declaración sigue como "
                    "temporal en el portal. Reintenta con --enviar.")
        raise SystemExit(1)
    elif resultado["estado"] == "desconocido":
        print_warning("Se firmó pero NO hay acuse que lo confirme: intenta "
                      "`sat-dm diot acuse` en unos minutos y verifica en el "
                      "portal antes de re-presentar.")
        raise SystemExit(1)
    else:
        print_success("Validación OK (no se envió). Usa --enviar para presentar.")
    if resultado.get("evidencia"):
        click.echo(f"  Evidencia: {', '.join(resultado['evidencia'])}")


@diot.command()
@click.option("--rfc", default=None,
              help="RFC del catálogo (toma la e.firma de `sat-dm empresas`)")
@click.option("--cer", type=click.Path(exists=True), default=None,
              help="Archivo .cer (si no usas el catálogo)")
@click.option("--key", type=click.Path(exists=True), default=None,
              help="Archivo .key (si no usas el catálogo)")
@click.option("--password", default=None,
              help="Contraseña de la clave privada (se pide oculta si falta)")
@click.option("--ejercicio", required=True, type=int, help="Ejercicio (p. ej. 2025)")
@click.option("--periodo", required=True, help="Mes de la declaración (1-12)")
@click.option("--tipo", default="001", show_default=True,
              help="Tipo de declaración (001=Normal)")
@click.option("--salida", default=None,
              help="Carpeta destino (default: {descargas}/diot/presentaciones/{RFC}/)")
@click.option("--ver-navegador", is_flag=True, default=False,
              help="Debug: mostrar el navegador (headful)")
def acuse(rfc, cer, key, password, ejercicio, periodo, tipo, salida,
          ver_navegador):
    """Descarga (reimprime) el acuse PDF de una DIOT ya presentada."""
    from ..portal.diot_presentacion import descargar_acuse_diot_fiel

    if rfc and not (cer and key):
        from . import config_store
        try:
            empresa = config_store.get_empresa(rfc.strip().upper())
        except KeyError:
            print_error(f"Empresa {rfc} no registrada. Usa 'sat-dm empresas add' "
                        "o pasa --cer/--key/--password.")
            raise SystemExit(1)
        cer = cer or empresa.get("cer_path")
        key = key or empresa.get("key_path")
        password = password or empresa.get("password")
    if not (cer and key):
        print_error("Falta la e.firma: pasa --rfc (catálogo) o --cer y --key.")
        raise SystemExit(1)
    if not password:
        password = click.prompt("  Contraseña de la clave privada", hide_input=True)

    rfc_etiqueta = (rfc or "").strip().upper()
    destino = salida or str(
        Path(get_descargas_dir()) / "diot" / "presentaciones"
        / (rfc_etiqueta or "sin_rfc") / str(ejercicio)
        / f"{int(periodo):02d}-{ejercicio}"
    )
    print_header(f"Acuse DIOT {ejercicio}-{int(periodo):02d} — "
                 f"{rfc_etiqueta or 'e.firma'}")
    resultado = descargar_acuse_diot_fiel(
        cer_path=cer, key_path=key, password=password,
        ejercicio=ejercicio, periodo=periodo, tipo_declaracion=tipo,
        directorio_salida=destino, headless=not ver_navegador,
    )
    if resultado:
        print_success(f"Acuse descargado: {resultado}")
    else:
        print_error("No se pudo capturar el acuse; revisa la evidencia en la "
                    "carpeta de salida.")
        raise SystemExit(1)
