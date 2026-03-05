"""
routers/auth.py — Endpoints de autenticación.
POST /auth/login  → autenticación con Supabase Auth
POST /auth/logout → cierre de sesión
GET  /auth/me     → datos del usuario actual y sus conjuntos
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from supabase import create_client, Client

from ph_saas.config import settings
from ph_saas.database import get_db
from ph_saas.dependencies import CurrentUser, get_current_user
from ph_saas.errors import ErrorMsg, http_401

router = APIRouter(prefix="/auth", tags=["auth"])

# ── Cliente Supabase (operaciones de Auth) ─────────────────────────────────────
_supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)


# ── Schemas de entrada ─────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ── POST /auth/login ───────────────────────────────────────────────────────────

@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """
    Autentica con Supabase Auth.
    Retorna: JWT de acceso + datos del usuario + lista de conjuntos.

    Si el usuario pertenece a más de un conjunto, el cliente debe:
    1. Mostrar selector de conjunto.
    2. Incluir el conjunto seleccionado en el header X-Conjunto-ID en requests posteriores.
    """
    try:
        response = _supabase.auth.sign_in_with_password(
            {"email": body.email, "password": body.password}
        )
    except Exception:
        raise http_401(ErrorMsg.AUTH_INVALID_CREDENTIALS)

    if not response.session:
        raise http_401(ErrorMsg.AUTH_INVALID_CREDENTIALS)

    session = response.session
    user = response.user

    # Buscar conjuntos del usuario
    from ph_saas.models.usuario_conjunto import UsuarioConjunto
    from ph_saas.models.conjunto import Conjunto

    app_metadata = user.app_metadata or {}
    is_superadmin = app_metadata.get("role") == "superadmin"

    conjuntos = []
    if not is_superadmin:
        uc_rows = (
            db.query(UsuarioConjunto)
            .join(Conjunto, Conjunto.id == UsuarioConjunto.conjunto_id)
            .filter(
                UsuarioConjunto.usuario_id == user.id,
                UsuarioConjunto.is_deleted == False,  # noqa: E712
                Conjunto.is_deleted == False,  # noqa: E712
            )
            .all()
        )
        conjuntos = [
            {
                "conjunto_id": str(uc.conjunto_id),
                "nombre": uc.conjunto.nombre,
                "rol": uc.rol,
            }
            for uc in uc_rows
        ]

    return {
        "data": {
            "access_token": session.access_token,
            "token_type": "Bearer",
            "expires_in": session.expires_in,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "is_superadmin": is_superadmin,
            },
            "conjuntos": conjuntos,
            # Si solo tiene un conjunto, se incluye para que el cliente no necesite selección
            "conjunto_activo": conjuntos[0] if len(conjuntos) == 1 else None,
        },
        "message": "ok",
    }


# ── POST /auth/logout ──────────────────────────────────────────────────────────

@router.post("/logout")
def logout(current_user: CurrentUser = Depends(get_current_user)):
    """Cierra la sesión actual en Supabase Auth."""
    try:
        _supabase.auth.sign_out()
    except Exception:
        pass  # El token ya expiró o fue invalidado — no es error
    return {"data": None, "message": "Sesión cerrada exitosamente"}


# ── GET /auth/me ───────────────────────────────────────────────────────────────

@router.get("/me")
def me(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retorna datos del usuario actual y sus conjuntos."""
    from ph_saas.models.usuario import Usuario
    from ph_saas.models.usuario_conjunto import UsuarioConjunto
    from ph_saas.models.conjunto import Conjunto

    # Perfil en nuestra tabla de usuarios
    usuario = (
        db.query(Usuario)
        .filter(Usuario.id == current_user.id, Usuario.is_deleted == False)  # noqa: E712
        .first()
    )

    conjuntos = []
    if not current_user.is_superadmin:
        uc_rows = (
            db.query(UsuarioConjunto)
            .join(Conjunto, Conjunto.id == UsuarioConjunto.conjunto_id)
            .filter(
                UsuarioConjunto.usuario_id == current_user.id,
                UsuarioConjunto.is_deleted == False,  # noqa: E712
                Conjunto.is_deleted == False,  # noqa: E712
            )
            .all()
        )
        conjuntos = [
            {
                "conjunto_id": str(uc.conjunto_id),
                "nombre": uc.conjunto.nombre,
                "rol": uc.rol,
            }
            for uc in uc_rows
        ]

    return {
        "data": {
            "id": str(current_user.id),
            "email": current_user.email,
            "is_superadmin": current_user.is_superadmin,
            "nombre": usuario.nombre if usuario else None,
            "cedula": usuario.cedula if usuario else None,
            "telefono_ws": usuario.telefono_ws if usuario else None,
            "conjuntos": conjuntos,
        },
        "message": "ok",
    }
