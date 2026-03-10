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

  GET  /panel/sa/usuarios                   -> SA: lista usuarios por conjunto
  POST /panel/sa/usuarios/crear             -> SA: crear usuario y asignar rol
  POST /panel/sa/usuarios/{uc_id}/rol       -> SA: cambiar rol
  POST /panel/sa/usuarios/{uc_id}/eliminar  -> SA: remover usuario de conjunto

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
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from supabase import create_client

from ph_saas.config import settings
from ph_saas.database import SessionLocal
from ph_saas.dependencies import _decode_jwt, CurrentUser
from ph_saas.models.conjunto import Conjunto
from ph_saas.models.configuracion_conjunto import ConfiguracionConjunto
from ph_saas.models.cuota import Cuota
from ph_saas.models.pago import Pago
from ph_saas.models.pago_detalle import PagoDetalle
from ph_saas.models.propiedad import Propiedad
from ph_saas.models.suscripcion import SuscripcionSaaS
from ph_saas.models.usuario import Usuario
from ph_saas.models.usuario_conjunto import UsuarioConjunto
from ph_saas.schemas.pago import PagoCreate, PagoDetalleIn
from ph_saas.services.pago_service import registrar_pago as _registrar_pago
from ph_saas.services.cartera_service import (
    get_cartera_antiguedad,
    get_estado_cuenta,
    get_resumen_cartera,
)
from ph_saas.services.pdf_service import (
    generar_cartera_pdf,
    generar_estado_cuenta_pdf,
    generar_paz_y_salvo_pdf,
)

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
# SUPERADMIN -- Usuarios por conjunto
# =============================================================================

@router.get("/panel/sa/usuarios", response_class=HTMLResponse)
def sa_usuarios(request: Request):
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
        cj_map = {c.id: c.nombre for c in conjuntos}

        uc_rows = (
            db.query(UsuarioConjunto)
            .join(Usuario, Usuario.id == UsuarioConjunto.usuario_id)
            .filter(
                UsuarioConjunto.is_deleted == False,  # noqa: E712
                Usuario.is_deleted == False,  # noqa: E712
            )
            .order_by(UsuarioConjunto.conjunto_id, Usuario.nombre)
            .all()
        )

        usuarios_data = [
            {
                "uc_id": str(uc.id),
                "nombre": f"{uc.usuario.nombre} {uc.usuario.apellido or ''}".strip(),
                "correo": uc.usuario.correo,
                "rol": uc.rol,
                "conjunto_nombre": cj_map.get(uc.conjunto_id, "—"),
            }
            for uc in uc_rows
        ]

        conjuntos_data = [{"id": str(c.id), "nombre": c.nombre} for c in conjuntos]

        response = templates.TemplateResponse("sa/usuarios.html", {
            "request": request,
            "user": user,
            "usuarios": usuarios_data,
            "conjuntos": conjuntos_data,
            "success": request.query_params.get("success"),
            "error": request.query_params.get("error"),
            "active": "sa_usuarios",
        })
    finally:
        db.close()
    return response


@router.post("/panel/sa/usuarios/crear")
def sa_crear_usuario(
    request: Request,
    nombre: str = Form(...),
    apellido: str = Form(""),
    email: str = Form(...),
    password: str = Form(...),
    conjunto_id: str = Form(...),
    rol: str = Form(...),
):
    user = _get_user(request)
    if not user or not user.is_superadmin:
        return _redir_login()

    if rol not in ROLES_VALIDOS:
        return _redir("/panel/sa/usuarios", error="Rol invalido")

    try:
        cj_uuid = uuid.UUID(conjunto_id.strip())
    except ValueError:
        return _redir("/panel/sa/usuarios", error="Conjunto invalido")

    db = SessionLocal()
    try:
        # Verificar que el conjunto existe
        cj = db.query(Conjunto).filter(
            Conjunto.id == cj_uuid, Conjunto.is_deleted == False  # noqa: E712
        ).first()
        if not cj:
            return _redir("/panel/sa/usuarios", error="Conjunto no encontrado")

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
                return _redir("/panel/sa/usuarios", error=f"Error creando usuario en Auth: {str(e)[:80]}")

            nuevo_user = Usuario(
                id=user_id,
                nombre=nombre.strip(),
                apellido=apellido.strip() or None,
                correo=correo,
            )
            db.add(nuevo_user)
            db.flush()

        dup = db.query(UsuarioConjunto).filter(
            UsuarioConjunto.usuario_id == user_id,
            UsuarioConjunto.conjunto_id == cj_uuid,
            UsuarioConjunto.is_deleted == False,  # noqa: E712
        ).first()
        if dup:
            return _redir("/panel/sa/usuarios", error="El usuario ya tiene un rol asignado en ese conjunto")

        uc = UsuarioConjunto(
            usuario_id=user_id,
            conjunto_id=cj_uuid,
            rol=rol,
        )
        db.add(uc)
        db.commit()
    except Exception:
        db.rollback()
        return _redir("/panel/sa/usuarios", error="Error al crear el usuario")
    finally:
        db.close()

    return _redir("/panel/sa/usuarios", success=f"Usuario {nombre.strip()} creado con rol {rol} en {cj.nombre}")


@router.post("/panel/sa/usuarios/{uc_id}/rol")
def sa_cambiar_rol_usuario(
    uc_id: uuid.UUID,
    request: Request,
    rol: str = Form(...),
):
    user = _get_user(request)
    if not user or not user.is_superadmin:
        return _redir_login()

    if rol not in ROLES_VALIDOS:
        return _redir("/panel/sa/usuarios", error="Rol invalido")

    db = SessionLocal()
    try:
        uc = db.query(UsuarioConjunto).filter(
            UsuarioConjunto.id == uc_id,
            UsuarioConjunto.is_deleted == False,  # noqa: E712
        ).first()
        if not uc:
            return _redir("/panel/sa/usuarios", error="Asignacion no encontrada")
        uc.rol = rol
        db.commit()
    except Exception:
        db.rollback()
        return _redir("/panel/sa/usuarios", error="Error al cambiar rol")
    finally:
        db.close()

    return _redir("/panel/sa/usuarios", success="Rol actualizado")


@router.post("/panel/sa/usuarios/{uc_id}/eliminar")
def sa_eliminar_usuario(
    uc_id: uuid.UUID,
    request: Request,
):
    user = _get_user(request)
    if not user or not user.is_superadmin:
        return _redir_login()

    db = SessionLocal()
    try:
        uc = db.query(UsuarioConjunto).filter(
            UsuarioConjunto.id == uc_id,
            UsuarioConjunto.is_deleted == False,  # noqa: E712
        ).first()
        if not uc:
            return _redir("/panel/sa/usuarios", error="Asignacion no encontrada")
        uc.is_deleted = True
        db.commit()
    except Exception:
        db.rollback()
        return _redir("/panel/sa/usuarios", error="Error al eliminar usuario")
    finally:
        db.close()

    return _redir("/panel/sa/usuarios", success="Usuario removido del conjunto")


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
                "propietario_id": str(p.propietario_id) if p.propietario_id else "",
                "propietario": (
                    f"{p.propietario.nombre} {p.propietario.apellido or ''}".strip()
                    if p.propietario_id and p.propietario else None
                ),
            }
            for p in propiedades
        ]

        user_rol = _get_user_rol(user.id, conjunto_id, db)

        # Propietarios para el dropdown (no-staff de este conjunto)
        staff_ids_prop = {
            row[0] for row in db.query(UsuarioConjunto.usuario_id).filter(
                UsuarioConjunto.conjunto_id == conjunto_id,
                UsuarioConjunto.is_deleted == False,  # noqa: E712
            ).all()
        }
        q_prop = db.query(Usuario).filter(Usuario.is_deleted == False)  # noqa: E712
        if staff_ids_prop:
            q_prop = q_prop.filter(~Usuario.id.in_(staff_ids_prop))
        usuarios_lista = [
            {"id": str(u.id), "nombre": f"{u.nombre} {u.apellido or ''}".strip()}
            for u in q_prop.order_by(Usuario.nombre).all()
        ]

        response = templates.TemplateResponse("app/propiedades.html", {
            "request": request,
            "user": user,
            "propiedades": props_data,
            "conjunto_nombre": cj_nombre,
            "user_rol": user_rol,
            "usuarios_lista": usuarios_lista,
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
    propietario_id: str = Form(""),
):
    user = _get_user(request)
    if not user:
        return _redir_login()
    conjunto_id = _get_conjunto_id(request)
    if not conjunto_id:
        return _redir("/panel/app/propiedades", error="Sin conjunto activo")

    prop_uuid = None
    if propietario_id.strip():
        try:
            prop_uuid = uuid.UUID(propietario_id.strip())
        except ValueError:
            return _redir("/panel/app/propiedades", error="Propietario invalido")

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
            propietario_id=prop_uuid,
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
    propietario_id: str = Form(""),
):
    user = _get_user(request)
    if not user:
        return _redir_login()
    conjunto_id = _get_conjunto_id(request)

    prop_uuid = None
    if propietario_id.strip():
        try:
            prop_uuid = uuid.UUID(propietario_id.strip())
        except ValueError:
            return _redir("/panel/app/propiedades", error="Propietario invalido")

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
        prop.propietario_id = prop_uuid
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
# ADMINISTRADOR -- Propietarios (Residentes)
# =============================================================================

@router.get("/panel/app/propietarios", response_class=HTMLResponse)
def app_propietarios(request: Request):
    user = _get_user(request)
    if not user:
        return _redir_login()
    conjunto_id = _get_conjunto_id(request)
    if not conjunto_id:
        return _redir_login()

    db = SessionLocal()
    try:
        uc_self = db.query(UsuarioConjunto).filter(
            UsuarioConjunto.usuario_id == user.id,
            UsuarioConjunto.conjunto_id == conjunto_id,
            UsuarioConjunto.is_deleted == False,  # noqa: E712
        ).first()
        if not uc_self or uc_self.rol != "Administrador":
            return _redir("/panel/app/propiedades", error="Solo administradores pueden gestionar propietarios")
        user_rol = uc_self.rol

        # IDs del personal del conjunto (no son propietarios)
        staff_ids = {
            row[0] for row in db.query(UsuarioConjunto.usuario_id).filter(
                UsuarioConjunto.conjunto_id == conjunto_id,
                UsuarioConjunto.is_deleted == False,  # noqa: E712
            ).all()
        }

        # Propietarios = usuarios NO staff de este conjunto
        q = db.query(Usuario).filter(Usuario.is_deleted == False)  # noqa: E712
        if staff_ids:
            q = q.filter(~Usuario.id.in_(staff_ids))
        residentes = q.order_by(Usuario.nombre).all()

        # Unidades asignadas a cada residente en este conjunto
        from ph_saas.models.propiedad import Propiedad as _Prop
        def _unidades(uid):
            return [
                p.numero_apartamento for p in db.query(_Prop).filter(
                    _Prop.propietario_id == uid,
                    _Prop.conjunto_id == conjunto_id,
                    _Prop.is_deleted == False,  # noqa: E712
                ).all()
            ]

        propietarios_data = [
            {
                "id": str(u.id),
                "nombre": u.nombre,
                "apellido": u.apellido or "",
                "cedula": u.cedula or "",
                "correo": u.correo if not u.correo.endswith("@ph-saas.local") else "",
                "telefono_ws": u.telefono_ws or "",
                "unidades": _unidades(u.id),
            }
            for u in residentes
        ]

        cj = db.query(Conjunto).filter(Conjunto.id == conjunto_id).first()
        response = templates.TemplateResponse("app/propietarios.html", {
            "request": request,
            "user": user,
            "propietarios": propietarios_data,
            "conjunto_nombre": cj.nombre if cj else "",
            "user_rol": user_rol,
            "success": request.query_params.get("success"),
            "error": request.query_params.get("error"),
            "active": "propietarios",
        })
    finally:
        db.close()
    return response


@router.post("/panel/app/propietarios/crear")
def app_crear_propietario(
    request: Request,
    nombre: str = Form(...),
    apellido: str = Form(""),
    cedula: str = Form(""),
    correo: str = Form(""),
    telefono_ws: str = Form(""),
):
    user = _get_user(request)
    if not user:
        return _redir_login()
    conjunto_id = _get_conjunto_id(request)
    if not conjunto_id:
        return _redir_login()

    db = SessionLocal()
    try:
        nuevo_id = uuid.uuid4()
        correo_final = correo.strip().lower() if correo.strip() else f"sin-correo-{nuevo_id}@ph-saas.local"

        if correo.strip():
            existe = db.query(Usuario).filter(
                Usuario.correo == correo_final, Usuario.is_deleted == False  # noqa: E712
            ).first()
            if existe:
                return _redir("/panel/app/propietarios", error="Ya existe un usuario con ese correo")

        nuevo = Usuario(
            id=nuevo_id,
            nombre=nombre.strip(),
            apellido=apellido.strip() or None,
            cedula=cedula.strip() or None,
            correo=correo_final,
            telefono_ws=telefono_ws.strip() or None,
        )
        db.add(nuevo)
        db.commit()
    except Exception:
        db.rollback()
        return _redir("/panel/app/propietarios", error="Error al crear propietario")
    finally:
        db.close()

    return _redir("/panel/app/propietarios", success=f"Propietario {nombre.strip()} creado")


@router.post("/panel/app/propietarios/{propietario_id}/editar")
def app_editar_propietario(
    propietario_id: uuid.UUID,
    request: Request,
    nombre: str = Form(...),
    apellido: str = Form(""),
    cedula: str = Form(""),
    correo: str = Form(""),
    telefono_ws: str = Form(""),
):
    user = _get_user(request)
    if not user:
        return _redir_login()
    conjunto_id = _get_conjunto_id(request)
    if not conjunto_id:
        return _redir_login()

    db = SessionLocal()
    try:
        p = db.query(Usuario).filter(
            Usuario.id == propietario_id, Usuario.is_deleted == False  # noqa: E712
        ).first()
        if not p:
            return _redir("/panel/app/propietarios", error="Propietario no encontrado")

        correo_final = correo.strip().lower() if correo.strip() else p.correo
        if correo.strip() and correo_final != p.correo:
            existe = db.query(Usuario).filter(
                Usuario.correo == correo_final,
                Usuario.id != propietario_id,
                Usuario.is_deleted == False,  # noqa: E712
            ).first()
            if existe:
                return _redir("/panel/app/propietarios", error="Ya existe otro usuario con ese correo")

        p.nombre = nombre.strip()
        p.apellido = apellido.strip() or None
        p.cedula = cedula.strip() or None
        p.correo = correo_final
        p.telefono_ws = telefono_ws.strip() or None
        db.commit()
    except Exception:
        db.rollback()
        return _redir("/panel/app/propietarios", error="Error al editar propietario")
    finally:
        db.close()

    return _redir("/panel/app/propietarios", success="Propietario actualizado")


@router.post("/panel/app/propietarios/{propietario_id}/eliminar")
def app_eliminar_propietario(propietario_id: uuid.UUID, request: Request):
    user = _get_user(request)
    if not user:
        return _redir_login()
    conjunto_id = _get_conjunto_id(request)
    if not conjunto_id:
        return _redir_login()

    db = SessionLocal()
    try:
        p = db.query(Usuario).filter(
            Usuario.id == propietario_id, Usuario.is_deleted == False  # noqa: E712
        ).first()
        if not p:
            return _redir("/panel/app/propietarios", error="Propietario no encontrado")
        # Desasignar de unidades en este conjunto
        for prop in db.query(Propiedad).filter(
            Propiedad.propietario_id == propietario_id,
            Propiedad.conjunto_id == conjunto_id,
            Propiedad.is_deleted == False,  # noqa: E712
        ).all():
            prop.propietario_id = None
        p.is_deleted = True
        db.commit()
    except Exception:
        db.rollback()
        return _redir("/panel/app/propietarios", error="Error al eliminar propietario")
    finally:
        db.close()

    return _redir("/panel/app/propietarios", success="Propietario eliminado")


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
        user_rol = _get_user_rol(user.id, conjunto_id, db)
        if user_rol == "Porteria":
            return _redir("/panel/app/propiedades", error="Sin permisos para esta seccion")

        config = db.query(ConfiguracionConjunto).filter(
            ConfiguracionConjunto.conjunto_id == conjunto_id
        ).first()

        cj = db.query(Conjunto).filter(Conjunto.id == conjunto_id).first()
        cj_nombre = cj.nombre if cj else ""

        # Si no existe configuracion, mostrar el formulario con valores por defecto
        if config:
            config_data = {
                "valor_cuota_estandar": str(config.valor_cuota_estandar),
                "dia_notificacion_mora": config.dia_notificacion_mora,
                "tasa_interes_mora": str(config.tasa_interes_mora),
                "permitir_interes": config.permitir_interes,
            }
        else:
            config_data = {
                "valor_cuota_estandar": "0.00",
                "dia_notificacion_mora": 5,
                "tasa_interes_mora": "0.00",
                "permitir_interes": True,
            }

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
            config = ConfiguracionConjunto(
                conjunto_id=conjunto_id,
                valor_cuota_estandar=valor_cuota_estandar,
                dia_generacion_cuota=1,
                dia_notificacion_mora=dia_notificacion_mora,
                tasa_interes_mora=tasa_interes_mora,
                permitir_interes=(permitir_interes == "on"),
            )
            db.add(config)
        else:
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


# =============================================================================
# ADMINISTRADOR / CONTADOR -- Pagos
# =============================================================================

@router.get("/panel/app/pagos", response_class=HTMLResponse)
def app_pagos(request: Request):
    user = _get_user(request)
    if not user:
        return _redir_login()
    conjunto_id = _get_conjunto_id(request)
    if not conjunto_id:
        return _redir_login()

    db = SessionLocal()
    try:
        user_rol = _get_user_rol(user.id, conjunto_id, db)
        if user_rol not in ("Administrador", "Contador"):
            return _redir("/panel/app/propiedades", error="Sin permisos para ver pagos")

        pagos = (
            db.query(Pago)
            .filter(Pago.conjunto_id == conjunto_id, Pago.is_deleted == False)  # noqa: E712
            .order_by(Pago.fecha_pago.desc(), Pago.created_at.desc())
            .limit(100)
            .all()
        )

        propiedades = (
            db.query(Propiedad)
            .filter(
                Propiedad.conjunto_id == conjunto_id,
                Propiedad.is_deleted == False,  # noqa: E712
                Propiedad.estado == "Activo",
            )
            .order_by(Propiedad.numero_apartamento)
            .all()
        )

        # Nombre del apartamento por propiedad_id
        prop_map = {str(p.id): p.numero_apartamento for p in propiedades}

        cj = db.query(Conjunto).filter(Conjunto.id == conjunto_id).first()
        cj_nombre = cj.nombre if cj else ""

        pagos_data = [
            {
                "id": str(p.id),
                "fecha_pago": p.fecha_pago.strftime("%d/%m/%Y"),
                "apartamento": prop_map.get(str(p.propiedad_id), "—"),
                "valor_total": str(p.valor_total),
                "metodo_pago": p.metodo_pago,
                "referencia": p.referencia or "—",
            }
            for p in pagos
        ]

        props_data = [
            {"id": str(p.id), "numero": p.numero_apartamento}
            for p in propiedades
        ]

        response = templates.TemplateResponse("app/pagos.html", {
            "request": request,
            "user": user,
            "pagos": pagos_data,
            "propiedades": props_data,
            "conjunto_nombre": cj_nombre,
            "user_rol": user_rol,
            "success": request.query_params.get("success"),
            "error": request.query_params.get("error"),
            "active": "pagos",
        })
    finally:
        db.close()
    return response


@router.post("/panel/app/pagos/registrar")
def app_registrar_pago(
    request: Request,
    propiedad_id: str = Form(...),
    fecha_pago: str = Form(...),
    valor_total: str = Form(...),
    metodo_pago: str = Form(...),
    referencia: str = Form(""),
):
    user = _get_user(request)
    if not user:
        return _redir_login()
    conjunto_id = _get_conjunto_id(request)
    if not conjunto_id:
        return _redir_login()

    db = SessionLocal()
    try:
        user_rol = _get_user_rol(user.id, conjunto_id, db)
        if user_rol not in ("Administrador", "Contador"):
            return _redir("/panel/app/propiedades", error="Sin permisos")

        try:
            prop_uuid = uuid.UUID(propiedad_id.strip())
            fecha = date.fromisoformat(fecha_pago.strip())
            monto = Decimal(valor_total.strip().replace(",", "."))
        except (ValueError, Exception):
            return _redir("/panel/app/pagos", error="Datos del pago invalidos")

        if monto <= Decimal("0"):
            return _redir("/panel/app/pagos", error="El monto debe ser mayor a cero")

        metodos_validos = {"Efectivo", "Transferencia", "PSE", "Otro"}
        if metodo_pago not in metodos_validos:
            return _redir("/panel/app/pagos", error="Metodo de pago invalido")

        # Obtener cuotas pendientes ordenadas de mas antigua a mas nueva
        cuotas = (
            db.query(Cuota)
            .filter(
                Cuota.conjunto_id == conjunto_id,
                Cuota.propiedad_id == prop_uuid,
                Cuota.is_deleted == False,  # noqa: E712
                Cuota.estado.in_(["Pendiente", "Parcial", "Vencida"]),
            )
            .order_by(Cuota.fecha_vencimiento.asc())
            .all()
        )

        if not cuotas:
            return _redir("/panel/app/pagos", error="La propiedad no tiene cuotas pendientes")

        # Auto-distribuir pago (primero cuotas mas antiguas)
        from sqlalchemy import func as _func
        remaining = monto
        detalles: list[PagoDetalleIn] = []
        for cuota in cuotas:
            if remaining <= Decimal("0"):
                break
            row = (
                db.query(
                    _func.coalesce(_func.sum(PagoDetalle.monto_a_interes), Decimal("0")),
                    _func.coalesce(_func.sum(PagoDetalle.monto_a_capital), Decimal("0")),
                )
                .filter(PagoDetalle.cuota_id == cuota.id)
                .one()
            )
            interes_pendiente = cuota.interes_generado - row[0]
            capital_pendiente = cuota.valor_base - row[1]
            deuda_total = interes_pendiente + capital_pendiente
            if deuda_total <= Decimal("0"):
                continue
            abono = min(remaining, deuda_total)
            detalles.append(PagoDetalleIn(cuota_id=cuota.id, monto_aplicado=abono))
            remaining -= abono

        pago_in = PagoCreate(
            propiedad_id=prop_uuid,
            fecha_pago=fecha,
            valor_total=monto,
            metodo_pago=metodo_pago,
            referencia=referencia.strip() or None,
            detalles=detalles,
        )
        _registrar_pago(db, conjunto_id, pago_in)

        msg = "Pago registrado correctamente"
        if remaining > Decimal("0"):
            msg += f" — saldo a favor: ${remaining:,.2f}"
    except Exception as exc:
        db.rollback()
        return _redir("/panel/app/pagos", error=f"Error al registrar pago: {str(exc)[:100]}")
    finally:
        db.close()

    return _redir("/panel/app/pagos", success=msg)


# =============================================================================
# TODOS LOS ROLES APP -- Reportes PDF
# =============================================================================

@router.get("/panel/app/reportes", response_class=HTMLResponse)
def app_reportes(request: Request):
    user = _get_user(request)
    if not user:
        return _redir_login()
    conjunto_id = _get_conjunto_id(request)
    if not conjunto_id:
        return _redir_login()

    db = SessionLocal()
    try:
        user_rol = _get_user_rol(user.id, conjunto_id, db)
        if not user_rol:
            return _redir("/panel/app/propiedades", error="Sin permisos")

        propiedades = (
            db.query(Propiedad)
            .filter(
                Propiedad.conjunto_id == conjunto_id,
                Propiedad.is_deleted == False,  # noqa: E712
            )
            .order_by(Propiedad.numero_apartamento)
            .all()
        )

        cj = db.query(Conjunto).filter(Conjunto.id == conjunto_id).first()
        cj_nombre = cj.nombre if cj else ""

        props_data = [
            {
                "id": str(p.id),
                "numero": p.numero_apartamento,
                "propietario": (
                    f"{p.propietario.nombre} {p.propietario.apellido or ''}".strip()
                    if p.propietario_id and p.propietario else None
                ),
            }
            for p in propiedades
        ]

        response = templates.TemplateResponse("app/reportes.html", {
            "request": request,
            "user": user,
            "propiedades": props_data,
            "conjunto_nombre": cj_nombre,
            "user_rol": user_rol,
            "success": request.query_params.get("success"),
            "error": request.query_params.get("error"),
            "active": "reportes",
        })
    finally:
        db.close()
    return response


@router.get("/panel/app/reportes/estado-cuenta/{propiedad_id}")
def app_reporte_estado_cuenta(propiedad_id: uuid.UUID, request: Request):
    user = _get_user(request)
    if not user:
        return _redir_login()
    conjunto_id = _get_conjunto_id(request)
    if not conjunto_id:
        return _redir("/panel/app/reportes", error="Sin conjunto activo")

    db = SessionLocal()
    try:
        user_rol = _get_user_rol(user.id, conjunto_id, db)
        if not user_rol:
            return _redir("/panel/app/reportes", error="Sin permisos")
        pdf = generar_estado_cuenta_pdf(db, conjunto_id, propiedad_id)
    finally:
        db.close()

    if pdf is None:
        return _redir("/panel/app/reportes", error="Propiedad no encontrada")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=estado_cuenta_{propiedad_id}.pdf"},
    )


@router.get("/panel/app/reportes/paz-y-salvo/{propiedad_id}")
def app_reporte_paz_y_salvo(propiedad_id: uuid.UUID, request: Request):
    user = _get_user(request)
    if not user:
        return _redir_login()
    conjunto_id = _get_conjunto_id(request)
    if not conjunto_id:
        return _redir("/panel/app/reportes", error="Sin conjunto activo")

    db = SessionLocal()
    try:
        user_rol = _get_user_rol(user.id, conjunto_id, db)
        if not user_rol:
            return _redir("/panel/app/reportes", error="Sin permisos")
        pdf = generar_paz_y_salvo_pdf(db, conjunto_id, propiedad_id)
    finally:
        db.close()

    if pdf is None:
        return _redir("/panel/app/reportes", error="Propiedad no encontrada")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=paz_y_salvo_{propiedad_id}.pdf"},
    )


@router.get("/panel/app/reportes/cartera")
def app_reporte_cartera(request: Request):
    user = _get_user(request)
    if not user:
        return _redir_login()
    conjunto_id = _get_conjunto_id(request)
    if not conjunto_id:
        return _redir("/panel/app/reportes", error="Sin conjunto activo")

    db = SessionLocal()
    try:
        user_rol = _get_user_rol(user.id, conjunto_id, db)
        if user_rol not in ("Administrador", "Contador"):
            return _redir("/panel/app/reportes", error="Sin permisos para este reporte")
        pdf = generar_cartera_pdf(db, conjunto_id)
    finally:
        db.close()

    if pdf is None:
        return _redir("/panel/app/reportes", error="Error al generar el reporte de cartera")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline; filename=cartera.pdf"},
    )


# =============================================================================
# PORTERIA -- Consulta de estado de apartamentos
# =============================================================================

@router.get("/panel/app/consulta", response_class=HTMLResponse)
def app_consulta(request: Request, buscar: str = ""):
    user = _get_user(request)
    if not user:
        return _redir_login()
    conjunto_id = _get_conjunto_id(request)
    if not conjunto_id:
        return _redir_login()

    db = SessionLocal()
    try:
        user_rol = _get_user_rol(user.id, conjunto_id, db)
        if not user_rol:
            return _redir_login()

        cj = db.query(Conjunto).filter(Conjunto.id == conjunto_id).first()
        cj_nombre = cj.nombre if cj else ""

        # Resumen global
        resumen = get_resumen_cartera(db, conjunto_id)

        # Listado de morosos con antigüedad
        antiguedad = get_cartera_antiguedad(db, conjunto_id)
        morosos = [
            {
                "id": str(item.propiedad_id),
                "numero": item.numero_apartamento,
                "dias_mora": item.dias_mora_max,
                "rango": item.rango,
                "saldo_total": str(item.saldo_total),
            }
            for item in sorted(antiguedad, key=lambda x: x.dias_mora_max, reverse=True)
        ]

        # Consulta de apartamento específico
        consulta_resultado = None
        buscar = buscar.strip()
        if buscar:
            prop = (
                db.query(Propiedad)
                .filter(
                    Propiedad.conjunto_id == conjunto_id,
                    Propiedad.is_deleted == False,  # noqa: E712
                    Propiedad.numero_apartamento.ilike(f"%{buscar}%"),
                )
                .first()
            )
            if prop:
                estado = get_estado_cuenta(db, conjunto_id, prop.id)
                if estado:
                    propietario_nombre = ""
                    if prop.propietario_id and prop.propietario:
                        propietario_nombre = f"{prop.propietario.nombre} {prop.propietario.apellido or ''}".strip()
                    consulta_resultado = {
                        "numero": estado.numero_apartamento,
                        "propietario": propietario_nombre,
                        "total_deuda": str(estado.total_deuda),
                        "saldo_a_favor": str(estado.saldo_a_favor_disponible),
                        "al_dia": estado.total_deuda == 0,
                        "cuotas_pendientes": [
                            {
                                "periodo": c.periodo,
                                "vencimiento": c.fecha_vencimiento.strftime("%d/%m/%Y"),
                                "saldo": str(c.saldo_pendiente),
                                "estado": c.estado,
                            }
                            for c in estado.cuotas
                            if c.estado != "Pagada" and c.saldo_pendiente > 0
                        ],
                    }
            else:
                consulta_resultado = {"error": f'No se encontró apartamento "{buscar}"'}

        response = templates.TemplateResponse("app/consulta.html", {
            "request": request,
            "user": user,
            "user_rol": user_rol,
            "conjunto_nombre": cj_nombre,
            "resumen": resumen,
            "morosos": morosos,
            "consulta_resultado": consulta_resultado,
            "buscar": buscar,
            "active": "consulta",
        })
    finally:
        db.close()
    return response
