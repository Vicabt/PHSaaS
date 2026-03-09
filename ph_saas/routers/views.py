"""
routers/views.py -- Pantallas HTML del sistema (Tailwind + Alpine.js).

Rutas:
  GET  /                                    -> Login
  POST /panel/login                         -> Procesar login
  GET  /panel/logout                        -> Cerrar sesion

  GET  /panel/sa/conjuntos                  -> SA: lista conjuntos
  POST /panel/sa/conjuntos/crear            -> SA: crear conjunto
  POST /panel/sa/conjuntos/{id}/editar      -> SA: editar
  POST /panel/sa/conjuntos/{id}/eliminar    -> SA: eliminar

  GET  /panel/sa/suscripciones              -> SA: gestion suscripciones
  POST /panel/sa/suscripciones/{id}/crear   -> SA: crear suscripcion
  POST /panel/sa/suscripciones/{id}/pagar   -> SA: registrar pago (extiende 1 mes)
  POST /panel/sa/suscripciones/{id}/suspender -> SA: suspender
  POST /panel/sa/suscripciones/{id}/activar -> SA: activar

  GET  /panel/app/propiedades               -> AD: lista propiedades
  POST /panel/app/propiedades/crear         -> AD: crear
  POST /panel/app/propiedades/{id}/editar   -> AD: editar
  POST /panel/app/propiedades/{id}/eliminar -> AD: eliminar

  GET  /panel/app/usuarios                  -> AD: lista usuarios
  POST /panel/app/usuarios/crear            -> AD: crear usuario
  POST /panel/app/usuarios/{id}/rol         -> AD: cambiar rol
  POST /panel/app/usuarios/{id}/eliminar    -> AD: eliminar del conjunto

  GET  /panel/app/configuracion             -> AD: ver configuracion
  POST /panel/app/configuracion             -> AD: guardar
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from supabase import create_client

from ph_saas.config import settings
from ph_saas.database import SessionLocal
from ph_saas.dependencies import _decode_jwt, CurrentUser
from ph_saas.models.conjunto import Conjunto
from ph_saas.models.configuracion_conjunto import ConfiguracionConjunto
from ph_saas.models.propiedad import Propiedad
from ph_saas.models.suscripcion import SuscripcionSaaS
from ph_saas.models.usuario import Usuario
from ph_saas.models.usuario_conjunto import UsuarioConjunto

router = APIRouter(tags=["vistas"])
templates = Jinja2Templates(directory="ph_saas/templates")

COOKIE_TOKEN = "ph_token"
COOKIE_CONJUNTO = "ph_conjunto_id"
ROLES_VALIDOS = ["Administrador", "Contador", "Porteria"]

_supabase_admin = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
_supabase_anon = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)


# -- Helpers -------------------------------------------------------------------

def _get_user(request: Request) -> Optional[CurrentUser]:
    token = request.cookies.get(COOKIE_TOKEN)
    if not token:
        return None
    try:
        payload = _decode_jwt(token)
        return CurrentUser(payload)
    except Exception:
        return None


def _get_conjunto_id(request: Request) -> Optional[uuid.UUID]:
    raw = request.cookies.get(COOKIE_CONJUNTO)
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


def _redir_login(msg: str = "Sesion expirada") -> RedirectResponse:
    r = RedirectResponse(url=f"/?error={msg}", status_code=302)
    r.delete_cookie(COOKIE_TOKEN)
    r.delete_cookie(COOKIE_CONJUNTO)
    return r


def _redir(path: str, success: str = None, error: str = None) -> RedirectResponse:
    params = []
    if success:
        params.append(f"success={success}")
    if error:
        params.append(f"error={error}")
    qs = ("?" + "&".join(params)) if params else ""
    return RedirectResponse(url=f"{path}{qs}", status_code=302)


def _get_user_rol(user_id: uuid.UUID, conjunto_id: Optional[uuid.UUID], db) -> str:
    """Retorna el rol del usuario en el conjunto activo, o '' si no aplica."""
    if not conjunto_id:
        return ""
    uc = db.query(UsuarioConjunto).filter(
        UsuarioConjunto.usuario_id == user_id,
        UsuarioConjunto.conjunto_id == conjunto_id,
        UsuarioConjunto.is_deleted == False,  # noqa: E712
    ).first()
    return uc.rol if uc else ""


# == GET / -- Login =============================================================

@router.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    user = _get_user(request)
    if user:
        if user.is_superadmin:
            return RedirectResponse(url="/panel/sa/conjuntos", status_code=302)
        return RedirectResponse(url="/panel/app/propiedades", status_code=302)
    error = request.query_params.get("error")
    return templates.TemplateResponse("login.html", {"request": request, "error": error})


# == POST /panel/login ==========================================================

@router.post("/panel/login")
def do_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    try:
        resp = _supabase_anon.auth.sign_in_with_password({"email": email, "password": password})
    except Exception:
        return _redir("/", error="Credenciales invalidas")

    if not resp.session:
        return _redir("/", error="Credenciales invalidas")

    token = resp.session.access_token
    user = resp.user
    app_metadata = user.app_metadata or {}
    is_superadmin = app_metadata.get("role") == "superadmin"

    if is_superadmin:
        r = RedirectResponse(url="/panel/sa/conjuntos", status_code=302)
        r.set_cookie(COOKIE_TOKEN, token, httponly=False, samesite="lax", max_age=3600)
        return r

    # Para admin: buscar conjuntos disponibles
    db = SessionLocal()
    try:
        uc_rows = (
            db.query(UsuarioConjunto)
            .join(Conjunto, Conjunto.id == UsuarioConjunto.conjunto_id)
            .filter(
                UsuarioConjunto.usuario_id == uuid.UUID(str(user.id)),
                UsuarioConjunto.is_deleted == False,  # noqa: E712
                Conjunto.is_deleted == False,  # noqa: E712
            )
            .all()
        )
    finally:
        db.close()

    if not uc_rows:
        return _redir("/", error="Usuario sin conjuntos asignados")

    r = RedirectResponse(url="/panel/app/propiedades", status_code=302)
    r.set_cookie(COOKIE_TOKEN, token, httponly=False, samesite="lax", max_age=3600)
    # Para Fase 1 tomamos el primer conjunto (o el unico)
    r.set_cookie(COOKIE_CONJUNTO, str(uc_rows[0].conjunto_id), samesite="lax", max_age=3600)
    return r


# == GET /panel/logout ==========================================================

@router.get("/panel/logout")
def logout():
    r = RedirectResponse(url="/", status_code=302)
    r.delete_cookie(COOKIE_TOKEN)
    r.delete_cookie(COOKIE_CONJUNTO)
    return r


# =============================================================================
# SUPERADMIN -- Conjuntos
# =============================================================================

@router.get("/panel/sa/conjuntos", response_class=HTMLResponse)
def sa_conjuntos(request: Request):
    user = _get_user(request)
    if not user or not user.is_superadmin:
        return _redir_login()

    db = SessionLocal()
    try:
        conjuntos = (
            db.query(Conjunto)
            .filter(Conjunto.is_deleted == False)  # noqa: E712
            .order_by(Conjunto.nombre)
            .all()
        )
        sus_map = {
            c.id: db.query(SuscripcionSaaS).filter(SuscripcionSaaS.conjunto_id == c.id).first()
            for c in conjuntos
        }
        response = templates.TemplateResponse("sa/conjuntos.html", {
            "request": request,
            "user": user,
            "conjuntos": conjuntos,
            "sus_map": sus_map,
            "success": request.query_params.get("success"),
            "error": request.query_params.get("error"),
            "active": "conjuntos",
        })
    finally:
        db.close()
    return response


@router.post("/panel/sa/conjuntos/crear")
def sa_crear_conjunto(
    request: Request,
    nombre: str = Form(...),
    nit: str = Form(""),
    direccion: str = Form(""),
    ciudad: str = Form(""),
):
    user = _get_user(request)
    if not user or not user.is_superadmin:
        return _redir_login()

    db = SessionLocal()
    try:
        existe = db.query(Conjunto).filter(
            Conjunto.nombre == nombre.strip(),
            Conjunto.is_deleted == False,  # noqa: E712
        ).first()
        if existe:
            return _redir("/panel/sa/conjuntos", error="Ya existe un conjunto con ese nombre")

        nuevo = Conjunto(
            nombre=nombre.strip(),
            nit=nit.strip() or None,
            direccion=direccion.strip() or None,
            ciudad=ciudad.strip() or None,
        )
        db.add(nuevo)
        db.flush()
        config = ConfiguracionConjunto(
            conjunto_id=nuevo.id,
            valor_cuota_estandar=Decimal("0.00"),
            dia_generacion_cuota=1,
            dia_notificacion_mora=5,
            tasa_interes_mora=Decimal("0.00"),
            permitir_interes=True,
        )
        db.add(config)
        db.commit()
    except Exception:
        db.rollback()
        return _redir("/panel/sa/conjuntos", error="Error al crear el conjunto")
    finally:
        db.close()

    return _redir("/panel/sa/conjuntos", success=f"Conjunto creado: {nombre.strip()}")


@router.post("/panel/sa/conjuntos/{conjunto_id}/editar")
def sa_editar_conjunto(
    conjunto_id: uuid.UUID,
    request: Request,
    nombre: str = Form(...),
    nit: str = Form(""),
    direccion: str = Form(""),
    ciudad: str = Form(""),
):
    user = _get_user(request)
    if not user or not user.is_superadmin:
        return _redir_login()

    db = SessionLocal()
    try:
        cj = db.query(Conjunto).filter(
            Conjunto.id == conjunto_id, Conjunto.is_deleted == False  # noqa: E712
        ).first()
        if not cj:
            return _redir("/panel/sa/conjuntos", error="Conjunto no encontrado")

        dup = db.query(Conjunto).filter(
            Conjunto.nombre == nombre.strip(),
            Conjunto.id != conjunto_id,
            Conjunto.is_deleted == False,  # noqa: E712
        ).first()
        if dup:
            return _redir("/panel/sa/conjuntos", error="Ya existe otro conjunto con ese nombre")

        cj.nombre = nombre.strip()
        cj.nit = nit.strip() or None
        cj.direccion = direccion.strip() or None
        cj.ciudad = ciudad.strip() or None
        db.commit()
    except Exception:
        db.rollback()
        return _redir("/panel/sa/conjuntos", error="Error al editar el conjunto")
    finally:
        db.close()

    return _redir("/panel/sa/conjuntos", success=f"Conjunto actualizado: {nombre.strip()}")


@router.post("/panel/sa/conjuntos/{conjunto_id}/eliminar")
def sa_eliminar_conjunto(conjunto_id: uuid.UUID, request: Request):
    user = _get_user(request)
    if not user or not user.is_superadmin:
        return _redir_login()

    db = SessionLocal()
    try:
        cj = db.query(Conjunto).filter(
            Conjunto.id == conjunto_id, Conjunto.is_deleted == False  # noqa: E712
        ).first()
        if not cj:
            return _redir("/panel/sa/conjuntos", error="Conjunto no encontrado")
        cj.is_deleted = True
        db.commit()
    except Exception:
        db.rollback()
        return _redir("/panel/sa/conjuntos", error="Error al eliminar")
    finally:
        db.close()

    return _redir("/panel/sa/conjuntos", success="Conjunto eliminado")


# =============================================================================
# SUPERADMIN -- Suscripciones
# =============================================================================

@router.get("/panel/sa/suscripciones", response_class=HTMLResponse)
def sa_suscripciones(request: Request):
    user = _get_user(request)
    if not user or not user.is_superadmin:
        return _redir_login()

    db = SessionLocal()
    try:
        conjuntos = (
            db.query(Conjunto)
            .filter(Conjunto.is_deleted == False)  # noqa: E712
            .order_by(Conjunto.nombre)
            .all()
        )
        sus_map = {
            c.id: db.query(SuscripcionSaaS).filter(SuscripcionSaaS.conjunto_id == c.id).first()
            for c in conjuntos
        }
        response = templates.TemplateResponse("sa/suscripciones.html", {
            "request": request,
            "user": user,
            "conjuntos": conjuntos,
            "sus_map": sus_map,
            "success": request.query_params.get("success"),
            "error": request.query_params.get("error"),
            "active": "suscripciones",
        })
    finally:
        db.close()
    return response


@router.post("/panel/sa/suscripciones/{conjunto_id}/crear")
def sa_crear_suscripcion(
    conjunto_id: uuid.UUID,
    request: Request,
    estado: str = Form("Activo"),
    fecha_vencimiento: date = Form(...),
    valor_mensual: Decimal = Form(...),
    observaciones: str = Form(""),
):
    user = _get_user(request)
    if not user or not user.is_superadmin:
        return _redir_login()

    db = SessionLocal()
    try:
        existe = db.query(SuscripcionSaaS).filter(
            SuscripcionSaaS.conjunto_id == conjunto_id
        ).first()
        if existe:
            return _redir("/panel/sa/suscripciones", error="Este conjunto ya tiene suscripcion")

        sus = SuscripcionSaaS(
            conjunto_id=conjunto_id,
            estado=estado,
            fecha_vencimiento=fecha_vencimiento,
            valor_mensual=valor_mensual,
            observaciones=observaciones.strip() or None,
        )
        db.add(sus)
        db.commit()
    except Exception:
        db.rollback()
        return _redir("/panel/sa/suscripciones", error="Error al crear suscripcion")
    finally:
        db.close()

    return _redir("/panel/sa/suscripciones", success="Suscripcion creada")


@router.post("/panel/sa/suscripciones/{conjunto_id}/pagar")
def sa_pagar_suscripcion(
    conjunto_id: uuid.UUID,
    request: Request,
    observaciones: str = Form(""),
):
    user = _get_user(request)
    if not user or not user.is_superadmin:
        return _redir_login()

    db = SessionLocal()
    try:
        sus = db.query(SuscripcionSaaS).filter(
            SuscripcionSaaS.conjunto_id == conjunto_id
        ).first()
        if not sus:
            return _redir("/panel/sa/suscripciones", error="No existe suscripcion para este conjunto")
        sus.fecha_vencimiento = sus.fecha_vencimiento + relativedelta(months=1)
        sus.estado = "Activo"
        if observaciones.strip():
            sus.observaciones = observaciones.strip()
        db.commit()
    except Exception:
        db.rollback()
        return _redir("/panel/sa/suscripciones", error="Error al registrar pago")
    finally:
        db.close()

    return _redir("/panel/sa/suscripciones", success="Pago registrado. Vencimiento extendido 1 mes")


@router.post("/panel/sa/suscripciones/{conjunto_id}/suspender")
def sa_suspender_suscripcion(conjunto_id: uuid.UUID, request: Request):
    user = _get_user(request)
    if not user or not user.is_superadmin:
        return _redir_login()

    db = SessionLocal()
    try:
        sus = db.query(SuscripcionSaaS).filter(
            SuscripcionSaaS.conjunto_id == conjunto_id
        ).first()
        if not sus:
            return _redir("/panel/sa/suscripciones", error="No existe suscripcion")
        if sus.estado == "Suspendido":
            return _redir("/panel/sa/suscripciones", error="La suscripcion ya esta suspendida")
        sus.estado = "Suspendido"
        db.commit()
    except Exception:
        db.rollback()
        return _redir("/panel/sa/suscripciones", error="Error al suspender")
    finally:
        db.close()

    return _redir("/panel/sa/suscripciones", success="Suscripcion suspendida")


@router.post("/panel/sa/suscripciones/{conjunto_id}/activar")
def sa_activar_suscripcion(conjunto_id: uuid.UUID, request: Request):
    user = _get_user(request)
    if not user or not user.is_superadmin:
        return _redir_login()

    db = SessionLocal()
    try:
        sus = db.query(SuscripcionSaaS).filter(
            SuscripcionSaaS.conjunto_id == conjunto_id
        ).first()
        if not sus:
            return _redir("/panel/sa/suscripciones", error="No existe suscripcion")
        if sus.estado == "Activo":
            return _redir("/panel/sa/suscripciones", error="La suscripcion ya esta activa")
        sus.estado = "Activo"
        db.commit()
    except Exception:
        db.rollback()
        return _redir("/panel/sa/suscripciones", error="Error al activar")
    finally:
        db.close()

    return _redir("/panel/sa/suscripciones", success="Suscripcion activada")


# =============================================================================
# ADMINISTRADOR -- Propiedades
# =============================================================================

@router.get("/panel/app/propiedades", response_class=HTMLResponse)
def app_propiedades(request: Request):
    user = _get_user(request)
    if not user:
        return _redir_login()
    conjunto_id = _get_conjunto_id(request)
    if not user.is_superadmin and not conjunto_id:
        return _redir_login("Sin conjunto asignado")

    db = SessionLocal()
    try:
        q = db.query(Propiedad).filter(Propiedad.is_deleted == False)  # noqa: E712
        if conjunto_id:
            q = q.filter(Propiedad.conjunto_id == conjunto_id)
        propiedades = q.order_by(Propiedad.numero_apartamento).all()

        cj_nombre = ""
        if conjunto_id:
            cj = db.query(Conjunto).filter(Conjunto.id == conjunto_id).first()
            cj_nombre = cj.nombre if cj else ""

        # Serializar para evitar detached instance errors
        props_data = [
            {
                "id": str(p.id),
                "numero_apartamento": p.numero_apartamento,
                "estado": p.estado,
                "propietario": (
                    f"{p.propietario.nombre} {p.propietario.apellido}"
                    if p.propietario_id and p.propietario else None
                ),
            }
            for p in propiedades
        ]

        user_rol = _get_user_rol(user.id, conjunto_id, db)
        response = templates.TemplateResponse("app/propiedades.html", {
            "request": request,
            "user": user,
            "propiedades": props_data,
            "conjunto_nombre": cj_nombre,
            "user_rol": user_rol,
            "success": request.query_params.get("success"),
            "error": request.query_params.get("error"),
            "active": "propiedades",
        })
    finally:
        db.close()
    return response


@router.post("/panel/app/propiedades/crear")
def app_crear_propiedad(
    request: Request,
    numero_apartamento: str = Form(...),
    estado: str = Form("Activo"),
):
    user = _get_user(request)
    if not user:
        return _redir_login()
    conjunto_id = _get_conjunto_id(request)
    if not conjunto_id:
        return _redir("/panel/app/propiedades", error="Sin conjunto activo")

    db = SessionLocal()
    try:
        dup = db.query(Propiedad).filter(
            Propiedad.conjunto_id == conjunto_id,
            Propiedad.numero_apartamento == numero_apartamento.strip(),
            Propiedad.is_deleted == False,  # noqa: E712
        ).first()
        if dup:
            return _redir("/panel/app/propiedades", error="Ya existe esa unidad en el conjunto")

        nueva = Propiedad(
            conjunto_id=conjunto_id,
            numero_apartamento=numero_apartamento.strip(),
            estado=estado,
        )
        db.add(nueva)
        db.commit()
    except Exception:
        db.rollback()
        return _redir("/panel/app/propiedades", error="Error al crear la unidad")
    finally:
        db.close()

    return _redir("/panel/app/propiedades", success=f"Unidad {numero_apartamento.strip()} creada")


@router.post("/panel/app/propiedades/{propiedad_id}/editar")
def app_editar_propiedad(
    propiedad_id: uuid.UUID,
    request: Request,
    numero_apartamento: str = Form(...),
    estado: str = Form("Activo"),
):
    user = _get_user(request)
    if not user:
        return _redir_login()
    conjunto_id = _get_conjunto_id(request)

    db = SessionLocal()
    try:
        q = db.query(Propiedad).filter(
            Propiedad.id == propiedad_id, Propiedad.is_deleted == False  # noqa: E712
        )
        if conjunto_id:
            q = q.filter(Propiedad.conjunto_id == conjunto_id)
        prop = q.first()
        if not prop:
            return _redir("/panel/app/propiedades", error="Unidad no encontrada")

        prop.numero_apartamento = numero_apartamento.strip()
        prop.estado = estado
        db.commit()
    except Exception:
        db.rollback()
        return _redir("/panel/app/propiedades", error="Error al editar")
    finally:
        db.close()

    return _redir("/panel/app/propiedades", success="Unidad actualizada")


@router.post("/panel/app/propiedades/{propiedad_id}/eliminar")
def app_eliminar_propiedad(propiedad_id: uuid.UUID, request: Request):
    user = _get_user(request)
    if not user:
        return _redir_login()
    conjunto_id = _get_conjunto_id(request)

    db = SessionLocal()
    try:
        q = db.query(Propiedad).filter(
            Propiedad.id == propiedad_id, Propiedad.is_deleted == False  # noqa: E712
        )
        if conjunto_id:
            q = q.filter(Propiedad.conjunto_id == conjunto_id)
        prop = q.first()
        if not prop:
            return _redir("/panel/app/propiedades", error="Unidad no encontrada")
        prop.is_deleted = True
        db.commit()
    except Exception:
        db.rollback()
        return _redir("/panel/app/propiedades", error="Error al eliminar")
    finally:
        db.close()

    return _redir("/panel/app/propiedades", success="Unidad eliminada")


# =============================================================================
# ADMINISTRADOR -- Usuarios
# =============================================================================

@router.get("/panel/app/usuarios", response_class=HTMLResponse)
def app_usuarios(request: Request):
    user = _get_user(request)
    if not user:
        return _redir_login()
    conjunto_id = _get_conjunto_id(request)
    if not user.is_superadmin and not conjunto_id:
        return _redir_login()

    db = SessionLocal()
    try:
        # Solo Administrador puede gestionar usuarios
        uc_self = db.query(UsuarioConjunto).filter(
            UsuarioConjunto.usuario_id == user.id,
            UsuarioConjunto.conjunto_id == conjunto_id,
            UsuarioConjunto.is_deleted == False,  # noqa: E712
        ).first()
        if not uc_self or uc_self.rol != "Administrador":
            return _redir("/panel/app/propiedades", error="Solo administradores pueden gestionar usuarios")
        user_rol = uc_self.rol

        uc_rows = (
            db.query(UsuarioConjunto)
            .join(Usuario, Usuario.id == UsuarioConjunto.usuario_id)
            .filter(
                UsuarioConjunto.conjunto_id == conjunto_id,
                UsuarioConjunto.is_deleted == False,  # noqa: E712
                Usuario.is_deleted == False,  # noqa: E712
            )
            .all()
        )

        cj_nombre = ""
        if conjunto_id:
            cj = db.query(Conjunto).filter(Conjunto.id == conjunto_id).first()
            cj_nombre = cj.nombre if cj else ""

        # Serializar antes de cerrar sesion
        usuarios_data = [
            {
                "id": str(uc.usuario_id),
                "nombre": uc.usuario.nombre,
                "apellido": uc.usuario.apellido or "",
                "correo": uc.usuario.correo,
                "rol": uc.rol,
            }
            for uc in uc_rows
        ]

        response = templates.TemplateResponse("app/usuarios.html", {
            "request": request,
            "user": user,
            "usuarios": usuarios_data,
            "conjunto_nombre": cj_nombre,
            "user_rol": user_rol,
            "roles": ROLES_VALIDOS,
            "success": request.query_params.get("success"),
            "error": request.query_params.get("error"),
            "active": "usuarios",
        })
    finally:
        db.close()
    return response


@router.post("/panel/app/usuarios/crear")
def app_crear_usuario(
    request: Request,
    nombre: str = Form(...),
    apellido: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    rol: str = Form(...),
):
    user = _get_user(request)
    if not user:
        return _redir_login()
    conjunto_id = _get_conjunto_id(request)
    if not conjunto_id:
        return _redir_login()

    if rol not in ROLES_VALIDOS:
        return _redir("/panel/app/usuarios", error="Rol invalido")

    db = SessionLocal()
    try:
        correo = email.strip().lower()
        usuario_local = db.query(Usuario).filter(
            Usuario.correo == correo,
            Usuario.is_deleted == False,  # noqa: E712
        ).first()

        if usuario_local:
            user_id = usuario_local.id
        else:
            try:
                resp = _supabase_admin.auth.admin.create_user({
                    "email": correo,
                    "password": password,
                    "email_confirm": True,
                    "user_metadata": {
                        "nombre": nombre.strip(),
                        "apellido": apellido.strip(),
                    },
                })
                user_id = uuid.UUID(str(resp.user.id))
            except Exception as e:
                return _redir("/panel/app/usuarios", error=f"Error creando usuario en Auth: {str(e)[:80]}")

            nuevo_user = Usuario(
                id=user_id,
                nombre=nombre.strip(),
                apellido=apellido.strip(),
                correo=correo,
            )
            db.add(nuevo_user)
            db.flush()

        dup = db.query(UsuarioConjunto).filter(
            UsuarioConjunto.usuario_id == user_id,
            UsuarioConjunto.conjunto_id == conjunto_id,
            UsuarioConjunto.is_deleted == False,  # noqa: E712
        ).first()
        if dup:
            return _redir("/panel/app/usuarios", error="El usuario ya pertenece a este conjunto")

        uc = UsuarioConjunto(
            usuario_id=user_id,
            conjunto_id=conjunto_id,
            rol=rol,
        )
        db.add(uc)
        db.commit()
    except Exception:
        db.rollback()
        return _redir("/panel/app/usuarios", error="Error al crear el usuario")
    finally:
        db.close()

    return _redir("/panel/app/usuarios", success=f"Usuario {nombre.strip()} {apellido.strip()} creado con rol {rol}")


@router.post("/panel/app/usuarios/{usuario_id}/rol")
def app_cambiar_rol(
    usuario_id: uuid.UUID,
    request: Request,
    rol: str = Form(...),
):
    user = _get_user(request)
    if not user:
        return _redir_login()
    conjunto_id = _get_conjunto_id(request)
    if not conjunto_id:
        return _redir_login()

    if rol not in ROLES_VALIDOS:
        return _redir("/panel/app/usuarios", error="Rol invalido")

    db = SessionLocal()
    try:
        uc = db.query(UsuarioConjunto).filter(
            UsuarioConjunto.usuario_id == usuario_id,
            UsuarioConjunto.conjunto_id == conjunto_id,
            UsuarioConjunto.is_deleted == False,  # noqa: E712
        ).first()
        if not uc:
            return _redir("/panel/app/usuarios", error="Usuario no encontrado en este conjunto")
        uc.rol = rol
        db.commit()
    except Exception:
        db.rollback()
        return _redir("/panel/app/usuarios", error="Error al cambiar rol")
    finally:
        db.close()

    return _redir("/panel/app/usuarios", success="Rol actualizado")


@router.post("/panel/app/usuarios/{usuario_id}/eliminar")
def app_eliminar_usuario(usuario_id: uuid.UUID, request: Request):
    user = _get_user(request)
    if not user:
        return _redir_login()
    conjunto_id = _get_conjunto_id(request)
    if not conjunto_id:
        return _redir_login()

    db = SessionLocal()
    try:
        uc = db.query(UsuarioConjunto).filter(
            UsuarioConjunto.usuario_id == usuario_id,
            UsuarioConjunto.conjunto_id == conjunto_id,
            UsuarioConjunto.is_deleted == False,  # noqa: E712
        ).first()
        if not uc:
            return _redir("/panel/app/usuarios", error="Usuario no encontrado")
        uc.is_deleted = True
        db.commit()
    except Exception:
        db.rollback()
        return _redir("/panel/app/usuarios", error="Error al eliminar usuario")
    finally:
        db.close()

    return _redir("/panel/app/usuarios", success="Usuario removido del conjunto")


# =============================================================================
# ADMINISTRADOR -- Configuracion
# =============================================================================

@router.get("/panel/app/configuracion", response_class=HTMLResponse)
def app_configuracion(request: Request):
    user = _get_user(request)
    if not user:
        return _redir_login()
    conjunto_id = _get_conjunto_id(request)
    if not conjunto_id:
        return _redir_login()

    db = SessionLocal()
    try:
        config = db.query(ConfiguracionConjunto).filter(
            ConfiguracionConjunto.conjunto_id == conjunto_id
        ).first()

        cj = db.query(Conjunto).filter(Conjunto.id == conjunto_id).first()
        cj_nombre = cj.nombre if cj else ""

        config_data = None
        if config:
            config_data = {
                "valor_cuota_estandar": str(config.valor_cuota_estandar),
                "dia_notificacion_mora": config.dia_notificacion_mora,
                "tasa_interes_mora": str(config.tasa_interes_mora),
                "permitir_interes": config.permitir_interes,
            }

        user_rol = _get_user_rol(user.id, conjunto_id, db)
        response = templates.TemplateResponse("app/configuracion.html", {
            "request": request,
            "user": user,
            "config": config_data,
            "conjunto_nombre": cj_nombre,
            "user_rol": user_rol,
            "success": request.query_params.get("success"),
            "error": request.query_params.get("error"),
            "active": "configuracion",
        })
    finally:
        db.close()
    return response


@router.post("/panel/app/configuracion")
def app_guardar_configuracion(
    request: Request,
    valor_cuota_estandar: Decimal = Form(...),
    dia_notificacion_mora: int = Form(...),
    tasa_interes_mora: Decimal = Form(...),
    permitir_interes: str = Form("off"),
):
    user = _get_user(request)
    if not user:
        return _redir_login()
    conjunto_id = _get_conjunto_id(request)
    if not conjunto_id:
        return _redir_login()

    db = SessionLocal()
    try:
        config = db.query(ConfiguracionConjunto).filter(
            ConfiguracionConjunto.conjunto_id == conjunto_id
        ).first()
        if not config:
            return _redir("/panel/app/configuracion", error="Configuracion no encontrada")

        config.valor_cuota_estandar = valor_cuota_estandar
        config.dia_notificacion_mora = dia_notificacion_mora
        config.tasa_interes_mora = tasa_interes_mora
        config.permitir_interes = (permitir_interes == "on")
        db.commit()
    except Exception:
        db.rollback()
        return _redir("/panel/app/configuracion", error="Error al guardar configuracion")
    finally:
        db.close()

    return _redir("/panel/app/configuracion", success="Configuracion guardada correctamente")
