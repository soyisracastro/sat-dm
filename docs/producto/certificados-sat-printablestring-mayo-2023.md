# Certificados del SAT de mayo 2023: parseo estricto y rechazo en descarga masiva

**Nota técnica — 14 de agosto de 2026.** Para equipos que integran e.firma / CSD del SAT.
Se comparte abiertamente: aplícala si te sirve.

Todo lo que sigue está verificado contra el SAT en vivo con un certificado real de la
ventana afectada, no inferido.

---

## Resumen

Los certificados de e.firma emitidos por la autoridad certificadora
`A.C. del Servicio de Administración Tributaria` (ventana de mayo de 2023) tienen
**dos problemas independientes**, y conviene no confundirlos porque tienen remedios
distintos:

| # | Problema | Dónde vive | ¿Se puede arreglar del lado del cliente? |
|---|---|---|---|
| 1 | El certificado **no se puede parsear** con librerías ASN.1 estrictas | En tu código | **Sí** — este documento explica cómo |
| 2 | El **Web Service de descarga masiva del SAT lo rechaza** con `CodEstatus=305` | En el SAT | **No** |

El problema 1 lo causa un **único campo mal tipado en el DN del emisor**: un atributo
declarado como `PrintableString` que contiene bytes UTF-8. No tiene nada que ver con
los datos del contribuyente ni con su llave privada.

**Por qué vale la pena arreglar el 1 aunque el 2 no tenga remedio:** el certificado
**sí funciona** en los demás canales del SAT — login del portal por e.firma,
Constancia de Situación Fiscal, Opinión de Cumplimiento 32-D, descarga de CFDIs por
el portal, y el servicio de autenticación del propio Web Service. Todos verificados
en vivo (ver más abajo). Si tu producto solo consume descarga masiva, el problema 2
te bloquea igual; si tocas cualquier otro trámite, el arreglo de parseo desbloquea a
ese contribuyente sin mandarlo al SAT.

**Sobre el mensaje "tramita una e.firma nueva":** es correcto **solo** si el usuario
necesita descarga masiva por Web Service. Como diagnóstico general es engañoso — el
certificado sigue siendo válido y vigente para todo lo demás.

---

## Síntoma

En Python (`cryptography`, backend Rust):

```
ValueError: error parsing asn1 value: ParseError { kind: InvalidValue,
  location: [10, 0, "AttributeTypeValue::value", "AttributeValue::PrintableString"] }
```

El índice `10` es la posición del atributo dentro del RDN del **emisor**.

Si el código intenta DER y luego cae a PEM (patrón habitual: los `.cer` del SAT son DER,
pero algunos usuarios los convierten), el error que llega al usuario es el del **segundo**
intento y resulta doblemente engañoso:

```
Unable to load PEM file. See https://cryptography.io/en/latest/faq/... MalformedFraming
```

Habla de PEM cuando el archivo es DER, y no menciona qué archivo falló — en nuestro caso
el usuario asumió que el problema estaba en la `.key`, no en el `.cer`.

---

## Causa raíz

Certificado de ejemplo (e.firma real, renovada el 23-05-2023, vigente a 2027-05-23).
Salida de `openssl asn1parse -inform DER`, sección del emisor:

```
  58:d=5  l=  3 prim: OBJECT          :commonName
  63:d=5  l= 49 prim: UTF8STRING      :A.C. del Servicio de Administración Tributaria
 118:d=5  l=  3 prim: OBJECT          :organizationName
 123:d=5  l= 40 prim: UTF8STRING      :Servicio de Administración Tributaria
 318:d=5  l=  3 prim: OBJECT          :stateOrProvinceName
 323:d=5  l= 19 prim: UTF8STRING      :Ciudad de México
 348:d=5  l=  3 prim: OBJECT          :localityName
 353:d=5  l= 13 prim: UTF8STRING      :Cuauhtémoc
 395:d=5  l=  9 prim: OBJECT          :unstructuredName          (1.2.840.113549.1.9.2)
 406:d=5  l= 78 prim: PRINTABLESTRING :responsable: Administración Central de Servicios
                                       Tributarios al Contribuyente
                     ^^^^^^^^^^^^^^^   ^^^^^^^^^^^^^^ 0xC3 0xB3 = "ó"
```

Todos los demás campos acentuados del emisor están correctamente tipados como
`UTF8STRING`. **Solo `unstructuredName` quedó como `PrintableString`** — y
`PrintableString` (X.680, cláusula 41, tabla 10) admite exclusivamente:

```
A–Z  a–z  0–9  espacio  ' ( ) + , - . / : = ?
```

Los bytes `0xC3 0xB3` no están en ese conjunto. El certificado, estrictamente hablando,
está mal codificado — pero lo emitió el SAT y el SAT lo honra.

### Por qué OpenSSL sí y otros no

OpenSSL no valida el juego de caracteres al parsear un `PrintableString`: lee el TLV y
entrega los bytes. Los parsers modernos escritos con validación estricta —el `rust-asn1`
que usa `cryptography` ≥ 42, y varios equivalentes en otros lenguajes— rechazan el TLV,
y como el DN es parte de la estructura obligatoria del certificado, **falla la carga
completa**, no solo la lectura de ese campo.

Por eso el problema aparece "de golpe" al actualizar dependencias: el certificado no
cambió, cambió la tolerancia del parser.

### Alcance

- Afecta a certificados cuyo **emisor** es la CA con el DN acentuado. En nuestro corpus,
  los emitidos por `AC DEL SERVICIO DE ADMINISTRACION TRIBUTARIA` (sin acentos) y por
  `AUTORIDAD CERTIFICADORA` cargan sin problema.
- Coincide con la ventana que otros integradores reportan públicamente (certificados
  generados **entre el 3 y el 24 de mayo de 2023**), atribuida a una actualización de los
  certificados raíz del SAT. El ejemplo analizado se emitió el **23-05-2023**.
- El defecto vive en el DN del **emisor**, es decir, viene copiado de la CA. No depende
  del contribuyente ni de sus datos.

---

## Qué acepta y qué rechaza el SAT (verificado en vivo)

El certificado del ejemplo se probó contra cada canal del SAT. El resultado **no es
uniforme**, y esa es la parte que suele malinterpretarse:

| Canal del SAT | Resultado |
|---|---|
| Acuse de CERTISAT WEB (operación `230500502463`) | Emisión normal, vigencia 2023-05-23 → 2027-05-27, sin observaciones |
| Login del portal por e.firma (NIDP) | ✅ acepta |
| Constancia de Situación Fiscal · Opinión 32-D | ✅ descarga |
| Descarga de CFDIs por el portal (e.firma, sin captcha) | ✅ descarga XMLs |
| `autenticacion/autenticacion.svc` (token del WS) | ✅ emite token |
| **`SolicitaDescarga` (WS de descarga masiva)** | ❌ **`CodEstatus=305, Certificado Inválido`** |

Es decir: el certificado **está vivo y es válido** en la infraestructura del SAT, pero el
servicio de descarga masiva lo rechaza específicamente. No es revocación ni caducidad —
esos son códigos distintos (`304 Certificado Revocado o Caduco`).

### Cómo se descartó que fuera el cliente

El rechazo del `305` es fácil de atribuir por error al propio código. Se aisló así:

1. **Mismo certificado, `X509IssuerName` normalizado.** El DN del emisor de esta CA
   además trae UTF-8 doblemente codificado en sus `UTF8String` (`CuauhtÃ©moc`,
   `AdministraciÃ³n`), así que era sospechoso natural. Se reenvió la solicitud con ese
   campo corregido → **mismo `305`**. No es el `IssuerName`.
2. **Control con un certificado sano, mismo código y mismo flujo.** Una e.firma de otra
   CA, por la misma ruta de firma y el mismo envelope → **`SolicitaDescarga` aceptada,
   `IdSolicitud` emitido**. El cliente firma bien.
3. **Orden de validación del SAT.** Ojo al depurar: el SAT valida **parámetros antes que
   certificado**. Una solicitud con parámetros inválidos devuelve `301` y nunca llega a
   revisar el certificado — es fácil concluir "el certificado pasó" cuando en realidad
   ni se evaluó. Hay que llegar a una solicitud con parámetros válidos para que el `305`
   aparezca.

Conclusión: el `305` es del lado del SAT y no tiene remedio del lado del cliente. El
único camino para descarga masiva por WS con estos certificados es renovar la e.firma.
Todo lo demás sigue funcionando con el certificado actual.

---

## Corrección

La idea: **el TLV conserva la longitud, así que basta cambiar el byte del tag** de
`PrintableString` (`0x13`) a `UTF8String` (`0x0C`) sobre una copia en memoria. El
contenido ya es UTF-8 válido, no hay que recodificar nada ni desplazar ningún byte.

Para acotar el riesgo, solo se retipan valores que aparecen **inmediatamente después de un
OID** — la forma de un `AttributeTypeValue` dentro de un DN — en vez de barrer el buffer
entero.

```python
# Caracteres válidos en un PrintableString (X.680).
_PRINTABLE_VALIDOS = frozenset(
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 '()+,-./:=?"
)
TAG_OID, TAG_PRINTABLE, TAG_UTF8 = 0x06, 0x13, 0x0C


def reparar_printablestring_en_der(der: bytes) -> bytes | None:
    """Retipa a UTF8String los PrintableString del DN con bytes ilegales.

    Devuelve el DER corregido, o None si no había nada que corregir.
    """
    buf = bytearray(der)
    cambios = 0
    i = buf.find(TAG_OID)
    while i != -1:
        len_oid = buf[i + 1] if i + 1 < len(buf) else 0x80
        j = i + 2 + len_oid                      # TLV que sigue al OID
        if len_oid < 0x80 and j + 1 < len(buf) and buf[j] == TAG_PRINTABLE:
            largo, inicio = buf[j + 1], j + 2
            if largo == 0x81 and j + 2 < len(buf):   # forma larga de 1 byte
                largo, inicio = buf[j + 2], j + 3
            if largo < 0x80 and inicio + largo <= len(buf):
                if any(b not in _PRINTABLE_VALIDOS for b in buf[inicio:inicio + largo]):
                    buf[j] = TAG_UTF8
                    cambios += 1
        i = buf.find(TAG_OID, i + 1)
    return bytes(buf) if cambios else None
```

Uso, como **último recurso** (no como camino normal):

```python
try:
    cert = x509.load_der_x509_certificate(data)
except ValueError:
    reparado = reparar_printablestring_en_der(data)
    if reparado is None:
        raise
    cert = x509.load_der_x509_certificate(reparado)
```

### ⚠️ Lo crítico: no re-serializar el certificado

El certificado reparado sirve **solo para leer metadatos** (RFC, razón social, vigencia,
número de serie, llave pública). **Lo que se envíe al SAT tiene que ser el archivo
original, byte por byte.**

La CA firmó el `tbsCertificate` tal como venía, con el tag `0x13`. Si se manda el DER
retipado —por ejemplo en el `BinarySecurityToken` de WS-Security, o en el `Certificado`
de un CFDI— **la firma de la CA ya no verifica** y el SAT lo rechaza.

En la práctica esto significa que cualquier propiedad tipo `certificado_b64` debe salir de
los bytes leídos del disco, no de re-serializar el objeto parseado:

```python
# ❌ mal: con el cert reparado emite el tag corregido
der = cert.public_bytes(serialization.Encoding.DER)

# ✅ bien: los bytes originales del archivo
der = self._cert_der
```

Es una trampa silenciosa: con certificados sanos ambas rutas dan lo mismo, así que el bug
solo aparece con los certificados afectados — justo los que se quería arreglar.

### Notas para otros lenguajes

El enfoque es independiente del stack; lo que cambia es dónde aparece el rechazo.

- **.NET** (`X509Certificate2`): históricamente tolerante vía CryptoAPI, pero
  `AsnDecoder`/`X500DistinguishedName` en modo estricto sí valida. Misma reparación sobre
  el `byte[]` antes de construir el certificado.
- **Java** (`CertificateFactory`): tolerante en el parseo, pero
  `X500Principal.getName(RFC2253)` puede fallar o devolver el valor en hex. Si solo se lee
  el subject, suele no hacer falta reparar.
- **Go** (`crypto/x509`): `encoding/asn1` es estricto con `PrintableString`; misma
  reparación sobre el slice.
- **Node** (`node-forge`, `pkijs`): varía por librería; `pkijs` es el más estricto.

### Cómo detectar el caso en producción

Un certificado afectado cumple las tres:

1. `openssl x509 -inform DER -in cert.cer -noout -issuer` funciona.
2. El parser propio falla con un error de ASN.1 que menciona `PrintableString`.
3. `openssl asn1parse -inform DER -in cert.cer | grep PRINTABLESTRING` muestra un valor
   con bytes no ASCII.

Vale la pena diferenciarlo en la UI tanto de un "archivo corrupto" o "contraseña
incorrecta" como del rechazo del SAT. Son tres mensajes distintos:

- **No se puede leer el archivo** → problema de parseo, se arregla con este documento.
- **`CodEstatus=305` en descarga masiva** → el SAT rechaza el certificado *para ese
  servicio*. Aquí sí aplica sugerir la renovación de la e.firma, pero conviene decir
  para qué: el certificado sigue sirviendo para el resto de los trámites.
- **`CodEstatus=304`** → ese sí es revocado o caduco, y es otra conversación.

La diferencia importa: un contribuyente al que se le dice "tu certificado es inválido,
tramita otro" cuando lo único que no le funciona es un canal, pierde una vuelta al SAT
que quizá no necesitaba.

---

## Estado en TodoConta

**Parseo (problema 1):** resuelto en `sat_descarga/core/fiel.py` (PR #190).
`_load_certificate` intenta DER → PEM → DER reparado, `certificate_b64` sale siempre de
los bytes originales, y si los tres intentos fallan el error es en español y nombra el
`.cer` en vez de filtrar el mensaje de PEM. Cubierto por tests, incluyendo uno de
integración que inyecta el defecto en un certificado de prueba sin alterarle la longitud.

**Rechazo del SAT (problema 2):** no tiene arreglo del lado del cliente. En TodoConta el
canal primario para e.firma es el portal (scraping sin captcha), no el Web Service, así
que estos contribuyentes operan con normalidad: descarga de CFDIs, CSF, 32-D. La descarga
masiva por WS queda como la única función que exige renovar la e.firma.

## Referencias

- ITU-T X.680, cláusula 41 y tabla 10 — juego de caracteres de `PrintableString`.
- RFC 5280 §4.1.2.4 — `Name` / `DirectoryString` en certificados X.509.
- `cryptography` (pyca) — validación estricta vía `rust-asn1` desde la v42.
