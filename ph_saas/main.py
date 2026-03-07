"""
main.py — Punto de entrada de la aplicación FastAPI.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ph_saas.config import settings
from ph_saas.middleware.tenant import TenantMiddleware
from ph_saas.routers import auth, conjuntos, propiedades, suscripciones, views
from ph_saas.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan: startup / shutdown ───────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    from ph_saas.dependencies import _get_jwks
    logger.info(f"Iniciando {settings.APP_NAME} ({settings.ENVIRONMENT})")
    # Prefetch JWKS en thread para cachear antes del primer request
    try:
        await asyncio.to_thread(_get_jwks)
        logger.info("JWKS precargado correctamente")
    except Exception as e:
        logger.warning(f"No se pudo precargar JWKS: {e}")
    start_scheduler()
    yield
    stop_scheduler()
    logger.info(f"{settings.APP_NAME} detenido")


# ── Instancia de la aplicación ─────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Sistema de administración de conjuntos residenciales — SaaS",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)


# ── Middlewares ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else [settings.APP_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tenant middleware — SIEMPRE después de CORS
app.add_middleware(TenantMiddleware)


# ── Archivos estáticos ─────────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory="ph_saas/static"), name="static")


# ── Routers ────────────────────────────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(conjuntos.router)
app.include_router(propiedades.router)
app.include_router(suscripciones.router)
app.include_router(views.router)

# Los demás routers se agregan en Fases 2-4:
# from ph_saas.routers import cuotas, pagos, cartera, reportes, internal
# app.include_router(cuotas.router)
# app.include_router(pagos.router)
# ...


# ── Health check ───────────────────────────────────────────────────────────────

@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "app": settings.APP_NAME}
