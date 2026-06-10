"""Tests para webservice.descarga._extraer_zip — extracción segura (anti zip-slip)."""

import io
import zipfile

import pytest

from sat_descarga.webservice.descarga import _extraer_zip


def _zip_en_memoria(miembros: dict[str, str]) -> bytes:
    """Construye un ZIP con {nombre_de_miembro: contenido}."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for nombre, contenido in miembros.items():
            zf.writestr(nombre, contenido)
    return buf.getvalue()


class TestExtraerZip:

    def test_extrae_zip_normal(self, tmp_path):
        zip_bytes = _zip_en_memoria({
            "uuid-1.xml": "<cfdi/>",
            "uuid-2.xml": "<cfdi/>",
        })
        total = _extraer_zip(zip_bytes, tmp_path, "PAQUETE-1")
        assert total == 2
        assert (tmp_path / "PAQUETE-1" / "uuid-1.xml").exists()
        assert (tmp_path / "PAQUETE-1" / "uuid-2.xml").exists()

    def test_rechaza_ruta_relativa_que_escapa(self, tmp_path):
        zip_bytes = _zip_en_memoria({"../fuera.xml": "<malicioso/>"})
        with pytest.raises(RuntimeError, match="ruta\\s+insegura"):
            _extraer_zip(zip_bytes, tmp_path, "PAQUETE-EVIL")
        assert not (tmp_path / "fuera.xml").exists()

    def test_rechaza_escape_profundo(self, tmp_path):
        zip_bytes = _zip_en_memoria({"../../../../tmp/evil.xml": "<malicioso/>"})
        with pytest.raises(RuntimeError, match="ruta\\s+insegura"):
            _extraer_zip(zip_bytes, tmp_path, "PAQUETE-EVIL")

    def test_subcarpetas_dentro_del_paquete_si_se_permiten(self, tmp_path):
        zip_bytes = _zip_en_memoria({"carpeta/uuid.xml": "<cfdi/>"})
        total = _extraer_zip(zip_bytes, tmp_path, "PAQUETE-2")
        assert total == 1
        assert (tmp_path / "PAQUETE-2" / "carpeta" / "uuid.xml").exists()

    def test_zip_corrupto_lanza_runtime_error(self, tmp_path):
        with pytest.raises(RuntimeError, match="corrupto"):
            _extraer_zip(b"esto no es un zip", tmp_path, "PAQUETE-3")
