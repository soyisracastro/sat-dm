# Certificados del SAT rechazados por parsers ASN.1 estrictos (mayo 2023)

**Nota técnica — 14 de agosto de 2026.** Para equipos que integran e.firma / CSD del SAT.
Se comparte abiertamente: aplícala si te sirve.

---

## Resumen

Un subconjunto de certificados de e.firma emitidos por la autoridad certificadora
`A.C. del Servicio de Administración Tributaria` **es rechazado por librerías de
criptografía con validación ASN.1 estricta**, mientras que OpenSSL y el propio SAT
los aceptan sin problema.

La causa es un **único campo mal tipado en el DN del emisor**: un atributo declarado
como `PrintableString` que contiene bytes UTF-8. No hay nada malo con el certificado
del contribuyente, ni con su llave privada, ni con su vigencia.

**Consecuencia práctica:** varios sistemas contables muestran a estos certificados
como inválidos y le piden al contribuyente tramitar una e.firma nueva ante el SAT.
**No es necesario.** El trámite es evitable con un cambio acotado del lado del cliente.

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

## El certificado es válido: verificación contra el SAT

Antes de pedirle a un contribuyente que renueve su e.firma, conviene comprobar contra la
fuente. Con el certificado del ejemplo:

1. **Acuse de CERTISAT WEB** (operación `230500502463`): el SAT certifica la entrega del
   certificado serie `00001000000600353820`, con vigencia del **23-05-2023 al 23-05-2027**,
   revocando el anterior. Emisión normal, sin observaciones.
2. **Autenticación contra el Web Service de descarga masiva** (`autenticacion/autenticacion.svc`),
   firmando el `Timestamp` con esa llave y adjuntando ese certificado en el `BinarySecurityToken`:
   **el SAT emitió token**.

Es decir: el SAT acepta el certificado en su propio canal autenticado. El rechazo ocurre
íntegramente del lado del cliente.

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

Vale la pena diferenciarlo en la UI de un "archivo corrupto" o "contraseña incorrecta":
el usuario que ve *"tu certificado es inválido, tramita otro"* pierde una vuelta al SAT
por un problema que no es suyo.

---

## Estado en TodoConta

Implementado en `sat_descarga/core/fiel.py` (PR #190). `_load_certificate` intenta
DER → PEM → DER reparado, `certificate_b64` sale siempre de los bytes originales, y si
los tres intentos fallan el error es en español y nombra el `.cer` en vez de filtrar el
mensaje de PEM. Cubierto por tests, incluyendo uno de integración que inyecta el defecto
en un certificado de prueba sin alterarle la longitud.

## Referencias

- ITU-T X.680, cláusula 41 y tabla 10 — juego de caracteres de `PrintableString`.
- RFC 5280 §4.1.2.4 — `Name` / `DirectoryString` en certificados X.509.
- `cryptography` (pyca) — validación estricta vía `rust-asn1` desde la v42.
