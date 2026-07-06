"""
Routers de FastAPI del agente local, partidos por dominio.

Cada router se crea con `APIRouter()` SIN prefix: las rutas completas viven en
cada decorador (p. ej. `@router.get("/empresas")`) para que sean idénticas a
las del monolito original (la UI y el CLI las consumen tal cual).

- webservice — Web Service oficial (FIEL/SOAP) + e-firma en sesión.
- portal     — scraping del portal SAT (CIEC + e.firma, jobs SSE + captcha).
- empresas   — catálogo de empresas + historial global.
- procesador — procesador de comprobantes (CFDI/Pagos/Nómina) + listas negras.
- utilidades — metadata, validación, organizador de XMLs.
- calculadoras — calculadoras fiscales/laborales + estado por empresa.
- system     — health, abrir en el SO, ajustes y auth de licencia (todoconta).
"""

from .webservice import router as webservice_router
from .portal import router as portal_router
from .empresas import router as empresas_router
from .procesador import router as procesador_router
from .utilidades import router as utilidades_router
from .calculadoras import router as calculadoras_router
from .system import router as system_router

__all__ = [
    "webservice_router",
    "portal_router",
    "empresas_router",
    "procesador_router",
    "utilidades_router",
    "calculadoras_router",
    "system_router",
]
