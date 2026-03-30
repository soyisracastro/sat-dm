"""
Fixtures compartidos para todos los tests.

pytest carga este archivo automáticamente. Los fixtures definidos aquí
están disponibles en cualquier test sin necesidad de importarlos.
"""

import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    """Ruta al directorio de fixtures."""
    return FIXTURES_DIR


@pytest.fixture
def test_cer():
    """Ruta al certificado de prueba (.cer)."""
    return str(FIXTURES_DIR / "test_fiel.cer")


@pytest.fixture
def test_key():
    """Ruta a la llave privada de prueba (.key)."""
    return str(FIXTURES_DIR / "test_fiel.key")


@pytest.fixture
def test_password():
    """Contraseña de la llave de prueba."""
    return "12345678"


@pytest.fixture
def test_rfc():
    """RFC del certificado de prueba."""
    return "XAXX010101000"
