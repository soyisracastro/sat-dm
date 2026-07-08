"""
Empaquetado ZIP del contenido del `.sdg` (CSD).

Certifica mete los PKCS#10 tipo SELLO (uno por sucursal) en un ZIP y ese ZIP es
el contenido que firma el CMS. Se reproduce el formato que usa Certifica/satcfdi:
deflate, `create_system=0`, `external_attr=0`, nombre de archivo en UTF-8 (bit 11
de flags). Portado de `satcfdi.zip` (MIT).
"""

import io
from collections import namedtuple
from zipfile import ZipFile, ZipInfo

ZipData = namedtuple("ZipData", "filename data")

_MASK_UTF_FILENAME = 1 << 11


class _ZipInfo(ZipInfo):
    def _encodeFilenameFlags(self):
        return self.filename.encode("utf-8"), self.flag_bits | _MASK_UTF_FILENAME


def zip_bytes(files: list[ZipData]) -> bytes:
    """Devuelve un ZIP (bytes) con los `files` dados. `data` puede ser bytes o un
    callable que reciba el stream de escritura (como en satcfdi)."""
    with io.BytesIO() as target:
        with ZipFile(target, "w") as myzip:
            myzip._seekable = False
            for f in files:
                zinfo = _ZipInfo(filename=f.filename)
                zinfo.compress_type = 8  # deflate
                zinfo.create_system = 0
                with myzip.open(zinfo, "w") as stream:
                    zinfo.external_attr = 0
                    if callable(f.data):
                        f.data(stream)
                    else:
                        stream.write(f.data)
        return target.getvalue()
