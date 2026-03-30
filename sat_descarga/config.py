"""
Configuración de endpoints y parámetros del SAT Descarga Masiva.
"""

ENDPOINTS = {
    "autenticacion": (
        "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx"
        "/Autenticacion/Autenticacion.svc"
    ),
    "solicita_descarga": (
        "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx"
        "/SolicitaDescargaService.svc"
    ),
    "verifica_solicitud": (
        "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx"
        "/VerificaSolicitudDescargaService.svc"
    ),
    "descarga_masiva": (
        "https://cfdidescargamasiva.clouda.sat.gob.mx"
        "/DescargaMasivaService.svc"
    ),
}

# Acciones SOAP (SOAPAction header)
# Nota: autenticacion usa el namespace .gob.mx (sin .sat); los demás usan .sat.gob.mx
SOAP_ACTIONS = {
    "autenticacion": "http://DescargaMasivaTerceros.gob.mx/IAutenticacion/Autentica",
    "solicita_descarga_emitidos": (
        "http://DescargaMasivaTerceros.sat.gob.mx"
        "/ISolicitaDescargaService/SolicitaDescargaEmitidos"
    ),
    "solicita_descarga_recibidos": (
        "http://DescargaMasivaTerceros.sat.gob.mx"
        "/ISolicitaDescargaService/SolicitaDescargaRecibidos"
    ),
    "solicita_descarga_folio": (
        "http://DescargaMasivaTerceros.sat.gob.mx"
        "/ISolicitaDescargaService/SolicitaDescargaFolio"
    ),
    "verifica_solicitud": (
        "http://DescargaMasivaTerceros.sat.gob.mx"
        "/IVerificaSolicitudDescargaService/VerificaSolicitudDescarga"
    ),
    "descarga_masiva": (
        "http://DescargaMasivaTerceros.sat.gob.mx/IDescargaMasivaTercerosService/Descargar"
    ),
}

# Namespaces XML comunes
NS = {
    "s": "http://schemas.xmlsoap.org/soap/envelope/",
    "u": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd",
    "o": "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd",
    "des": "http://DescargaMasivaTerceros.gob.mx",        # autenticacion
    "des2": "http://DescargaMasivaTerceros.sat.gob.mx",   # solicitud / verifica / descarga
    "xd": "http://www.w3.org/2000/09/xmldsig#",
}

# Reintentos por inestabilidad SSL del SAT
HTTP_RETRIES = 6
HTTP_BACKOFF_FACTOR = 1.5
HTTP_TIMEOUT = 60  # segundos

# Polling de verificación
POLL_INTERVAL_INITIAL = 30   # segundos
POLL_INTERVAL_MAX = 300      # 5 minutos máximo entre polls
POLL_BACKOFF_FACTOR = 1.5
POLL_MAX_ATTEMPTS = 100

# Tipos de descarga
TIPO_CFDI = "CFDI"
TIPO_METADATA = "Metadata"

# Tipos de comprobante
TIPO_EMITIDO = "E"
TIPO_RECIBIDO = "R"
