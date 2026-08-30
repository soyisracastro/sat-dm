"""Subcomandos `sat-dm ce`: contabilidad electrónica (Anexo 24).

- `sat-dm ce inventario` — revisa los ZIP (nomenclatura vs contenido del XML)
  sin tocar el portal.
- `sat-dm ce enviar`     — sube los ZIP al portal del SAT con e.firma. Por
  default solo valida: llega al modal de resumen y cancela. El envío real
  requiere --enviar.
"""

from pathlib import Path

import click

from .display import print_error, print_header, print_success, print_warning


def _expandir(rutas) -> list[Path]:
    """Archivos .zip a partir de rutas sueltas o carpetas.

    Las carpetas NO se recorren en profundidad a propósito: en los repos de
    papeles de trabajo suele haber ZIPs de respaldo colgando de la carpeta
    padre que no son envíos.
    """
    zips: list[Path] = []
    for r in rutas:
        p = Path(r)
        if p.is_dir():
            zips.extend(sorted(p.glob("*.zip")))
        else:
            zips.append(p)
    return zips


def _resolver_efirma(rfc, cer, key, password):
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
    return cer, key, password


@click.group("ce")
def contabilidad():
    """Contabilidad electrónica (Anexo 24): revisar y enviar los ZIP al SAT."""


@contabilidad.command("inventario")
@click.argument("rutas", nargs=-1, required=True,
                type=click.Path(exists=True))
def cmd_inventario(rutas):
    """Revisa los ZIP: nomenclatura, XML de adentro y coherencia entre ambos."""
    from ..portal.contabilidad_electronica import inventario

    zips = _expandir(rutas)
    if not zips:
        print_error("No encontré archivos .zip en esas rutas.")
        raise SystemExit(1)

    print_header(f"Contabilidad electrónica — {len(zips)} archivo(s)")
    filas = inventario(zips)
    malos = 0
    for f in filas:
        if f["problemas"]:
            malos += 1
            print_error(f"{f['archivo']}")
            for p in f["problemas"]:
                click.echo(f"      · {p}")
        else:
            click.echo(f"  ✓ {f['archivo']:32s} {f['tipo_desc']:34s} "
                       f"{f['anio']}-{f['mes']}  v{f['version']}")
    click.echo()
    if malos:
        print_warning(f"{malos} de {len(filas)} no pasan la revisión; "
                      "corrígelos antes de enviar.")
        raise SystemExit(1)
    print_success(f"Los {len(filas)} cuadran nombre y contenido.")


@contabilidad.command("enviar")
@click.argument("rutas", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("--rfc", default=None, help="Empresa del catálogo (resuelve la e.firma).")
@click.option("--cer", type=click.Path(exists=True), default=None)
@click.option("--key", type=click.Path(exists=True), default=None)
@click.option("--password", default=None, help="Contraseña de la clave privada.")
@click.option("--enviar", is_flag=True, help="Enviar de verdad (default: solo validar).")
@click.option("--si", is_flag=True, help="No pedir confirmación antes de enviar.")
@click.option("--sin-sellar", is_flag=True,
              help="No sellar los XML con la e.firma (el portal lo permite).")
@click.option("--motivo", default="mensual",
              help="Texto que debe contener el motivo del envío (default: mensual).")
@click.option("--salida", default=None,
              help="Dónde guardar los acuses (default: junto a cada ZIP).")
@click.option("--reintentos", default=8, show_default=True,
              help="Intentos por archivo ante errores transitorios del SAT.")
@click.option("--reenviar", is_flag=True,
              help="Mandar aunque el portal ya tenga el archivo (default: se omite).")
@click.option("--ver", is_flag=True, help="Mostrar el navegador.")
def cmd_enviar(rutas, rfc, cer, key, password, enviar, si, sin_sellar, motivo,
               salida, reintentos, reenviar, ver):
    """Sube los ZIP de contabilidad electrónica al portal del SAT."""
    from ..portal.contabilidad_electronica import EnviadorCE, inventario

    zips = _expandir(rutas)
    if not zips:
        print_error("No encontré archivos .zip en esas rutas.")
        raise SystemExit(1)

    filas = inventario(zips)
    if any(f["problemas"] for f in filas):
        print_error("Hay ZIPs que no pasan la revisión previa. "
                    "Corre 'sat-dm ce inventario' para el detalle.")
        raise SystemExit(1)

    rfc_lote = filas[0].get("rfc", "")
    print_header(f"Contabilidad electrónica — {rfc_lote} — "
                 f"{len(filas)} archivo(s) "
                 f"({'ENVÍO' if enviar else 'solo validación'})")
    for f in filas:
        click.echo(f"  · {f['archivo']:32s} {f['tipo_desc']:34s} "
                   f"{f['anio']}-{f['mes']}")
    click.echo()

    cer, key, password = _resolver_efirma(rfc or rfc_lote, cer, key, password)

    if enviar and not si:
        if not click.confirm(f"  ¿Enviar estos {len(filas)} archivos al SAT?",
                             default=False):
            click.echo("  Cancelado.")
            return

    envidor = EnviadorCE(headless=not ver, reintentos=reintentos,
                         progreso=lambda m: click.echo(f"  {m}"))
    try:
        res = envidor.enviar(cer, key, password, [f["path"] for f in filas],
                             sellar=not sin_sellar, enviar=enviar,
                             motivo=motivo, salida=salida,
                             omitir_enviados=not reenviar)
    except (ValueError, FileNotFoundError) as e:
        print_error(str(e))
        raise SystemExit(1)

    click.echo()
    for r in res.get("omitidos", []):
        click.echo(f"  – {r['archivo']} ya presentado ({r.get('estatus','')}); "
                   "se omitió")
    for r in res["enviados"]:
        if r.get("folio"):
            print_success(f"{r['archivo']} — folio {r['folio']} "
                          f"({r.get('intentos', 1)} intento(s))"
                          + (f" · acuse: {r['acuse']}" if r.get("acuse") else ""))
        else:
            click.echo(f"  ✓ {r['archivo']} validado (no enviado)")
    for r in res["fallidos"]:
        print_error(f"{r['archivo']} — {r.get('mensaje', 'sin detalle')[:160]}")

    if res["fallidos"]:
        raise SystemExit(1)
    if enviar:
        print_warning(
            "El acuse de RECEPCIÓN no ampara el cumplimiento: el SAT todavía "
            "valida el archivo. Verifica el acuse de aceptación o rechazo en "
            "Buzón Tributario › Contabilidad Electrónica › Consultas.")


@contabilidad.command("acuses")
@click.option("--rfc", default=None, help="Empresa del catálogo (resuelve la e.firma).")
@click.option("--cer", type=click.Path(exists=True), default=None)
@click.option("--key", type=click.Path(exists=True), default=None)
@click.option("--password", default=None)
@click.option("--anio", type=int, required=True, help="Ejercicio a consultar.")
@click.option("--mes-ini", type=int, default=1, show_default=True)
@click.option("--mes-fin", type=int, default=13, show_default=True,
              help="13 = ajuste al cierre.")
@click.option("--bajar", is_flag=True,
              help="Descargar los PDF de recepción y de aceptación/rechazo.")
@click.option("--salida", default=None, help="Carpeta donde guardar los acuses.")
@click.option("--ver", is_flag=True, help="Mostrar el navegador.")
def cmd_acuses(rfc, cer, key, password, anio, mes_ini, mes_fin, bajar, salida, ver):
    """Consulta el estatus de lo enviado (Recibido / Aceptado / Rechazado)."""
    from ..portal.contabilidad_electronica import ConsultorCE

    cer, key, password = _resolver_efirma(rfc, cer, key, password)
    print_header(f"Acuses de contabilidad electrónica — "
                 f"{(rfc or '').upper()} — {anio}")

    filas = ConsultorCE(headless=not ver,
                        progreso=lambda m: click.echo(f"  {m}")).consultar(
        cer, key, password, anio=anio, mes_ini=mes_ini, mes_fin=mes_fin,
        bajar_acuses=bajar, salida=salida)

    if not filas:
        print_warning("El portal no reporta envíos en ese rango.")
        return

    click.echo()
    for f in filas:
        marca = {"Aceptado": "✓", "Rechazado": "✗"}.get(f.get("estatus"), "·")
        click.echo(f"  {marca} {f.get('periodo',''):8s} "
                   f"{f.get('archivo',''):30s} {f.get('estatus',''):10s} "
                   f"{f.get('fecha','')}")
        if f.get("acuse_resultado"):
            click.echo(f"      resultado: {f['acuse_resultado']}")

    rechazados = [f for f in filas if f.get("estatus") == "Rechazado"]
    pendientes = [f for f in filas if f.get("estatus") == "Recibido"]
    click.echo()
    if rechazados:
        print_error(f"{len(rechazados)} rechazado(s): hay que corregir y reenviar.")
    if pendientes:
        print_warning(f"{len(pendientes)} en «Recibido»: el SAT aún los valida; "
                      "solo «Aceptado» ampara el cumplimiento.")
    if not rechazados and not pendientes:
        print_success(f"Los {len(filas)} envíos están Aceptados.")
