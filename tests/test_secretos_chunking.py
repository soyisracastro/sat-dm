"""
Chunking de blobs grandes en el backend keyring (`core/secretos`).

El Credential Manager de Windows (CredWrite) rechaza blobs de más de 2560 bytes
(WinError 1783); la sesión de Supabase (JWT + refresh token) lo excede
(TODOCONTA-DESKTOP-1G). `guardar_blob` parte los valores largos en pedazos bajo
el límite y `obtener_blob` los reensambla de forma transparente.

Usa el keyring en memoria del conftest (sin `SAT_DM_SECRETS_KEY`, el dispatch
cae al backend keyring, que es donde vive el chunking).
"""

import keyring

from sat_descarga.core import secretos

SERVICIO = "com.todoconta.test"
USUARIO = "session"


def test_blob_corto_roundtrip_sin_chunks():
    secretos.guardar_blob(SERVICIO, USUARIO, "hola")
    assert secretos.obtener_blob(SERVICIO, USUARIO) == "hola"
    # Se guarda directo, sin centinela ni entradas hermanas.
    assert keyring.get_password(SERVICIO, USUARIO) == "hola"
    assert keyring.get_password(SERVICIO, f"{USUARIO}__chunk0") is None


def test_blob_grande_roundtrip_en_chunks():
    valor = "x" * 5000  # > _CHUNK_CHARS → 5 pedazos
    secretos.guardar_blob(SERVICIO, USUARIO, valor)
    assert secretos.obtener_blob(SERVICIO, USUARIO) == valor
    # La entrada principal es el centinela; cada pedazo cabe en CredWrite.
    principal = keyring.get_password(SERVICIO, USUARIO)
    assert principal.startswith(secretos._CHUNK_MARCA)
    for i in range(5):
        pedazo = keyring.get_password(SERVICIO, f"{USUARIO}__chunk{i}")
        assert pedazo is not None
        assert len(pedazo) <= secretos._CHUNK_CHARS


def test_sobrescribir_grande_con_corto_limpia_chunks():
    secretos.guardar_blob(SERVICIO, USUARIO, "y" * 5000)
    secretos.guardar_blob(SERVICIO, USUARIO, "corto")
    assert secretos.obtener_blob(SERVICIO, USUARIO) == "corto"
    assert keyring.get_password(SERVICIO, f"{USUARIO}__chunk0") is None


def test_sobrescribir_grande_con_menos_chunks_limpia_sobrantes():
    secretos.guardar_blob(SERVICIO, USUARIO, "a" * 5000)   # 5 pedazos
    valor_nuevo = "b" * 2500                                # 3 pedazos
    secretos.guardar_blob(SERVICIO, USUARIO, valor_nuevo)
    assert secretos.obtener_blob(SERVICIO, USUARIO) == valor_nuevo
    assert keyring.get_password(SERVICIO, f"{USUARIO}__chunk2") is not None
    assert keyring.get_password(SERVICIO, f"{USUARIO}__chunk3") is None
    assert keyring.get_password(SERVICIO, f"{USUARIO}__chunk4") is None


def test_borrar_blob_elimina_todo():
    secretos.guardar_blob(SERVICIO, USUARIO, "z" * 5000)
    secretos.borrar_blob(SERVICIO, USUARIO)
    assert secretos.obtener_blob(SERVICIO, USUARIO) is None
    for i in range(5):
        assert keyring.get_password(SERVICIO, f"{USUARIO}__chunk{i}") is None


def test_chunk_faltante_devuelve_none():
    secretos.guardar_blob(SERVICIO, USUARIO, "w" * 5000)
    keyring.delete_password(SERVICIO, f"{USUARIO}__chunk1")
    # Secreto incompleto = no hay secreto (mismo contrato que "no existe").
    assert secretos.obtener_blob(SERVICIO, USUARIO) is None
