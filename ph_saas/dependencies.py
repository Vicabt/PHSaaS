"""
dependencies.py — Dependencias compartidas de FastAPI.
get_current_user: decodifica el JWT de Supabase y retorna datos del usuario.
require_role: fábrica de dependencias para control de acceso por rol.
"""

import uuid
from typing import Callable, Optional

import httpx
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwk, jwt
from sqlalchemy.orm import Session

from ph_saas.config import settings
from ph_saas.database import get_db
from ph_saas.errors import ErrorMsg, http_401, http_403

security = HTTPBearer()

# ── JWKS cache (Supabase publica clave pública para ES256) ─────────────────────

_jwks_cache: Optional[dict] = None


def _get_jwks() -> dict:
    """Obtiene y cachea las claves públicas JWKS de Supabase."""
    global _jwks_cache
    if _jwks_cache is None:
        try:
            url = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
            resp = httpx.get(url, timeout=10)
            resp.raise_for_status()
            _jwks_cache = resp.json()
        except Exception:
            _jwks_cache = {"keys": []}
    return _jwks_cache


def _decode_jwt(token: str) -> dict:
    """
    Decodifica y verifica un JWT de Supabase.
    Soporta HS256 (proyectos legacy) y ES256/RS256 (proyectos nuevos via JWKS).
    """
    try:
        header = jwt.get_unverified_header(token)
    except JWTError:
        raise JWTError("Header inválido")

    alg = header.get("alg", "HS256")

    if alg == "HS256":
        # Proyectos legacy: verificar con JWT_SECRET
        return jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    elif alg in ("ES256", "RS256"):
        # Proyectos nuevos: verificar con clave pública JWKS
        jwks = _get_jwks()
        kid = header.get("kid")
        keys = jwks.get("keys", [])

        # Buscar la clave que coincide con el kid del token
        key_data = next((k for k in keys if k.get("kid") == kid), None)
        if key_data is None and keys:
            key_data = keys[0]  # Fallback: usar la primera clave disponible

        if not key_data:
            raise JWTError("No se encontró clave pública JWKS")

        public_key = jwk.construct(key_data)
        return jwt.decode(
            token,
            public_key,
            algorithms=[alg],
            options={"verify_aud": False},
        )
    else:
        raise JWTError(f"Algoritmo no soportado: {alg}")


# ── Tipos de datos del usuario autenticado ─────────────────────────────────────

class CurrentUser:
    """Datos del usuario extraídos del JWT."""

    def __init__(self, payload: dict):
        self.id: uuid.UUID = uuid.UUID(payload["sub"])
        self.email: str = payload.get("email", "")
        # app_metadata.role = 'superadmin' para el superadmin
        app_metadata = payload.get("app_metadata", {})
        self.role: str = app_metadata.get("role", "")
        self.is_superadmin: bool = self.role == "superadmin"
        # conjunto_id puede venir en app_metadata (si es usuario de un solo conjunto)
        raw_cj = app_metadata.get("conjunto_id")
        self.conjunto_id: uuid.UUID | None = uuid.UUID(raw_cj) if raw_cj else None


# ── Dependencia: get_current_user ──────────────────────────────────────────────

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> CurrentUser:
    """
    Verifica el JWT de Supabase Auth y retorna el usuario actual.
    Lanza 401 si el token es inválido o expirado.
    """
    import logging
    _log = logging.getLogger("ph_saas.auth")

    token = credentials.credentials
    try:
        payload = _decode_jwt(token)
    except JWTError as e:
        _log.error("JWTError en get_current_user: %s: %s", type(e).__name__, str(e))
        error_msg = str(e).lower()
        if "expired" in error_msg:
            raise http_401(ErrorMsg.AUTH_TOKEN_EXPIRED)
        raise http_401(ErrorMsg.AUTH_NO_TOKEN)
    except Exception as e:
        _log.error("Exception inesperada en get_current_user: %s: %s", type(e).__name__, str(e))
        raise http_401(ErrorMsg.AUTH_NO_TOKEN)

    if not payload.get("sub"):
        raise http_401(ErrorMsg.AUTH_NO_TOKEN)

    return CurrentUser(payload)


def require_role(*allowed_roles: str) -> Callable:
    """
    Fábrica de dependencias para control de acceso por rol.

    SuperAdmin siempre pasa (bypass completo).
    Para otros roles, verifica en usuario_conjunto que el usuario tenga
    uno de los roles permitidos en el conjunto activo del request.

    Uso:
        @router.get("/api/propiedades")
        def listar(user = Depends(require_role("Administrador", "Contador"))):
            ...
    """

    def _dependency(
        request: Request,
        current_user: CurrentUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> CurrentUser:
        # SuperAdmin: bypass completo
        if current_user.is_superadmin:
            return current_user

        # Obtener conjunto_id inyectado por middleware/tenant.py
        conjunto_id: uuid.UUID | None = getattr(request.state, "conjunto_id", None)
        if not conjunto_id:
            raise http_403(ErrorMsg.AUTH_INSUFFICIENT_ROLE)

        # Importación diferida para evitar circular imports
        from ph_saas.models.usuario_conjunto import UsuarioConjunto

        uc = (
            db.query(UsuarioConjunto)
            .filter(
                UsuarioConjunto.usuario_id == current_user.id,
                UsuarioConjunto.conjunto_id == conjunto_id,
                UsuarioConjunto.is_deleted == False,  # noqa: E712
            )
            .first()
        )

        if not uc:
            raise http_403(ErrorMsg.AUTH_INSUFFICIENT_ROLE)

        if uc.rol not in allowed_roles:
            raise http_403(ErrorMsg.AUTH_INSUFFICIENT_ROLE)

        return current_user

    return _dependency


# ── Dependencia: solo SuperAdmin ───────────────────────────────────────────────

def require_superadmin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """
    Dependencia para endpoints /admin/* — exclusivos de SuperAdmin.
    """
    if not current_user.is_superadmin:
        raise http_403(ErrorMsg.AUTH_SUPERADMIN_ONLY)
    return current_user
