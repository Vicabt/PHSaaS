"""
middleware/tenant.py — COMPONENTE CRÍTICO del sistema.
Aislamiento multi-tenant + verificación de suscripción SaaS.

Flujo por request:
  JWT (Supabase Auth)
        ↓
  ¿rol == superadmin? → SÍ: bypass completo
                      → NO: extrae conjunto_id (JWT o header X-Conjunto-ID)
                            ↓ verifica usuario tiene acceso al conjunto
                            ↓ verifica suscripcion_saas.estado == 'Activo'
                            → Suspendido: HTTP 403
                            → Activo: inyecta conjunto_id en request.state
"""

import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from jose import JWTError

logger = logging.getLogger(__name__)

# Rutas que NO pasan por verificación de tenant
PUBLIC_PREFIXES = (
    "/auth/",
    "/internal/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
    "/static/",
    "/health",
    "/panel/",   # vistas HTML — gestionan su propia auth via cookies
)


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware de aislamiento multi-tenant.
    Inyecta request.state.conjunto_id en todos los requests autenticados no-superadmin.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # ── Rutas públicas/internas → pasar directo ────────────────────────────
        if any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES) or path == "/":
            return await call_next(request)

        # ── Leer token del header Authorization ───────────────────────────────
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Se requiere autenticación"},
            )

        import asyncio
        token = auth_header.removeprefix("Bearer ").strip()
        try:
            from ph_saas.dependencies import _decode_jwt
            payload = await asyncio.to_thread(_decode_jwt, token)
        except JWTError:
            return JSONResponse(
                status_code=401,
                content={"detail": "Sesion expirada. Por favor inicia sesion nuevamente"},
            )

        # ── SuperAdmin → bypass completo ───────────────────────────────────────
        app_metadata = payload.get("app_metadata", {})
        if app_metadata.get("role") == "superadmin":
            request.state.is_superadmin = True
            request.state.conjunto_id = None
            request.state.user_id = uuid.UUID(payload["sub"])
            return await call_next(request)

        # ── Extraer conjunto_id ────────────────────────────────────────────────
        # 1. Desde app_metadata del JWT (asignado al seleccionar conjunto en login)
        # 2. Desde header X-Conjunto-ID como fallback
        raw_conjunto_id = app_metadata.get("conjunto_id") or request.headers.get("X-Conjunto-ID")
        if not raw_conjunto_id:
            return JSONResponse(
                status_code=403,
                content={"detail": "No tienes permisos para realizar esta acción"},
            )

        try:
            conjunto_id = uuid.UUID(str(raw_conjunto_id))
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"detail": "conjunto_id inválido"},
            )

        user_id = uuid.UUID(payload["sub"])

        # ── Verificar acceso al conjunto y estado de suscripción ───────────────
        from ph_saas.database import SessionLocal
        from ph_saas.models.usuario_conjunto import UsuarioConjunto
        from ph_saas.models.suscripcion import SuscripcionSaaS

        db = SessionLocal()
        try:
            # Verificar que el usuario pertenece a este conjunto
            uc = (
                db.query(UsuarioConjunto)
                .filter(
                    UsuarioConjunto.usuario_id == user_id,
                    UsuarioConjunto.conjunto_id == conjunto_id,
                    UsuarioConjunto.is_deleted == False,  # noqa: E712
                )
                .first()
            )
            if not uc:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "No tienes permisos para realizar esta acción"},
                )

            # Verificar estado de suscripción SaaS
            suscripcion = (
                db.query(SuscripcionSaaS)
                .filter(SuscripcionSaaS.conjunto_id == conjunto_id)
                .first()
            )
            if not suscripcion or suscripcion.estado == "Suspendido":
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "El acceso a este conjunto está suspendido. Contacta al administrador del sistema"
                    },
                )

        except Exception as e:
            logger.error(f"[TenantMiddleware] Error verificando acceso: {e}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Error interno del servidor. Intenta nuevamente"},
            )
        finally:
            db.close()

        # ── Inyectar contexto en el request ───────────────────────────────────
        request.state.conjunto_id = conjunto_id
        request.state.user_id = user_id
        request.state.is_superadmin = False

        return await call_next(request)
