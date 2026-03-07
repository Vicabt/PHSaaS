"""
routers/conjuntos.py — CRUD de Conjuntos (SuperAdmin), Usuarios por conjunto y Configuración.

Rutas:
  /admin/conjuntos          → SA: CRUD conjuntos
  /api/usuarios             → AD: CRUD usuarios del conjunto activo
  /api/configuracion        → AD/CO: ver y editar configuración del conjunto
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from supabase import create_client, Client

from ph_saas.config import settings, BOGOTA_TZ
from ph_saas.database import get_db
from ph_saas.dependencies import CurrentUser, get_current_user, require_role, require_superadmin
from ph_saas.errors import ErrorMsg, http_400, http_404, http_409
from ph_saas.models.conjunto import Conjunto
from ph_saas.models.configuracion_conjunto import ConfiguracionConjunto
from ph_saas.models.suscripcion import SuscripcionSaaS
from ph_saas.models.usuario import Usuario
from ph_saas.models.usuario_conjunto import UsuarioConjunto
from ph_saas.schemas.conjunto import ConjuntoCreate, ConjuntoDetalle, ConjuntoOut, ConjuntoUpdate, SuscripcionCreate
from ph_saas.schemas.configuracion import ConfiguracionOut, ConfiguracionUpdate
from ph_saas.schemas.usuario import CambiarRolBody, UsuarioConjuntoOut, UsuarioCreate

router = APIRouter(tags=["conjuntos"])

# Cliente Supabase con service role (para gestión de usuarios de Auth)
_supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

ROLES_VALIDOS = {"Administrador", "Contador", "Porteria"}


# ══════════════════════════════════════════════════════════════════════════════
# /admin/conjuntos — Solo SuperAdmin
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/admin/conjuntos", response_model=list[ConjuntoOut])
def listar_conjuntos(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_superadmin),
):
    """Lista todos los conjuntos activos."""
    return (
        db.query(Conjunto)
        .filter(Conjunto.is_deleted == False)  # noqa: E712
        .order_by(Conjunto.nombre)
        .all()
    )


@router.post("/admin/conjuntos", response_model=ConjuntoDetalle, status_code=201)
def crear_conjunto(
    body: ConjuntoCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_superadmin),
):
    """
    Crea un nuevo conjunto.
    Si se incluye `suscripcion` en el body, crea también la suscripción SaaS.
    """
    # Verificar nombre único
    existe = (
        db.query(Conjunto)
        .filter(Conjunto.nombre == body.nombre, Conjunto.is_deleted == False)  # noqa: E712
        .first()
    )
    if existe:
        raise http_409(ErrorMsg.CONJUNTO_ALREADY_EXISTS)

    conjunto = Conjunto(
        nombre=body.nombre,
        nit=body.nit,
        direccion=body.direccion,
        ciudad=body.ciudad,
    )
    db.add(conjunto)
    db.flush()  # obtener conjunto.id antes de crear suscripción

    # Configuración por defecto (se puede personalizar después)
    config = ConfiguracionConjunto(
        conjunto_id=conjunto.id,
        valor_cuota_estandar=0,
        dia_generacion_cuota=1,
        dia_notificacion_mora=5,
        tasa_interes_mora=0,
        permitir_interes=True,
    )
    db.add(config)

    # Suscripción SaaS (opcional al momento de crear)
    suscripcion = body.suscripcion
    if suscripcion:
        sus = SuscripcionSaaS(
            conjunto_id=conjunto.id,
            estado=suscripcion.estado,
            fecha_vencimiento=suscripcion.fecha_vencimiento,
            valor_mensual=suscripcion.valor_mensual,
            observaciones=suscripcion.observaciones,
        )
        db.add(sus)

    db.commit()
    db.refresh(conjunto)
    return conjunto


@router.get("/admin/conjuntos/{conjunto_id}", response_model=ConjuntoDetalle)
def obtener_conjunto(
    conjunto_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_superadmin),
):
    conjunto = _get_conjunto_or_404(conjunto_id, db)
    return conjunto


@router.put("/admin/conjuntos/{conjunto_id}", response_model=ConjuntoOut)
def editar_conjunto(
    conjunto_id: uuid.UUID,
    body: ConjuntoUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_superadmin),
):
    conjunto = _get_conjunto_or_404(conjunto_id, db)

    if body.nombre and body.nombre != conjunto.nombre:
        existe = (
            db.query(Conjunto)
            .filter(Conjunto.nombre == body.nombre, Conjunto.is_deleted == False)  # noqa: E712
            .first()
        )
        if existe:
            raise http_409(ErrorMsg.CONJUNTO_ALREADY_EXISTS)
        conjunto.nombre = body.nombre

    if body.nit is not None:
        conjunto.nit = body.nit
    if body.direccion is not None:
        conjunto.direccion = body.direccion
    if body.ciudad is not None:
        conjunto.ciudad = body.ciudad

    db.commit()
    db.refresh(conjunto)
    return conjunto


@router.delete("/admin/conjuntos/{conjunto_id}", status_code=204)
def eliminar_conjunto(
    conjunto_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_superadmin),
):
    conjunto = _get_conjunto_or_404(conjunto_id, db)
    conjunto.is_deleted = True
    db.commit()


# ══════════════════════════════════════════════════════════════════════════════
# /api/usuarios — Administrador del conjunto activo
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/api/usuarios", response_model=list[UsuarioConjuntoOut])
def listar_usuarios(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("Administrador")),
):
    """Lista todos los usuarios activos del conjunto."""
    conjunto_id = current_user.conjunto_id
    rows = (
        db.query(UsuarioConjunto)
        .join(Usuario, Usuario.id == UsuarioConjunto.usuario_id)
        .filter(
            UsuarioConjunto.conjunto_id == conjunto_id,
            UsuarioConjunto.is_deleted == False,  # noqa: E712
            Usuario.is_deleted == False,  # noqa: E712
        )
        .all()
    )
    return [
        UsuarioConjuntoOut(
            id=uc.id,
            usuario_id=uc.usuario_id,
            conjunto_id=uc.conjunto_id,
            rol=uc.rol,
            nombre=uc.usuario.nombre,
            correo=uc.usuario.correo,
            cedula=uc.usuario.cedula,
            telefono_ws=uc.usuario.telefono_ws,
            created_at=uc.created_at,
        )
        for uc in rows
    ]


@router.post("/api/usuarios", response_model=UsuarioConjuntoOut, status_code=201)
def crear_usuario(
    body: UsuarioCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("Administrador")),
):
    """
    Crea un usuario en Supabase Auth y lo registra en el conjunto con el rol indicado.
    """
    conjunto_id = current_user.conjunto_id

    if body.rol not in ROLES_VALIDOS:
        raise http_400(f"Rol inválido. Valores permitidos: {', '.join(ROLES_VALIDOS)}")

    # Verificar si correo ya existe en la tabla usuario
    usuario_existente = (
        db.query(Usuario)
        .filter(Usuario.correo == body.correo, Usuario.is_deleted == False)  # noqa: E712
        .first()
    )

    if usuario_existente:
        # El usuario ya existe — verificar que no esté ya en este conjunto
        uc_existente = (
            db.query(UsuarioConjunto)
            .filter(
                UsuarioConjunto.usuario_id == usuario_existente.id,
                UsuarioConjunto.conjunto_id == conjunto_id,
                UsuarioConjunto.is_deleted == False,  # noqa: E712
            )
            .first()
        )
        if uc_existente:
            raise http_409("Este usuario ya pertenece al conjunto")
        usuario = usuario_existente
    else:
        # Crear en Supabase Auth
        try:
            auth_resp = _supabase.auth.admin.create_user({
                "email": body.correo,
                "password": body.password,
                "email_confirm": True,
            })
        except Exception as e:
            raise http_400(f"Error al crear usuario en Auth: {str(e)}")

        auth_user = auth_resp.user
        usuario = Usuario(
            id=uuid.UUID(str(auth_user.id)),
            nombre=body.nombre,
            correo=body.correo,
            cedula=body.cedula,
            telefono_ws=body.telefono_ws,
        )
        db.add(usuario)
        db.flush()

    # Asignar al conjunto con el rol
    uc = UsuarioConjunto(
        usuario_id=usuario.id,
        conjunto_id=conjunto_id,
        rol=body.rol,
    )
    db.add(uc)
    db.commit()
    db.refresh(uc)

    return UsuarioConjuntoOut(
        id=uc.id,
        usuario_id=uc.usuario_id,
        conjunto_id=uc.conjunto_id,
        rol=uc.rol,
        nombre=usuario.nombre,
        correo=usuario.correo,
        cedula=usuario.cedula,
        telefono_ws=usuario.telefono_ws,
        created_at=uc.created_at,
    )


@router.put("/api/usuarios/{usuario_id}/rol", response_model=UsuarioConjuntoOut)
def cambiar_rol(
    usuario_id: uuid.UUID,
    body: CambiarRolBody,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("Administrador")),
):
    """Cambia el rol de un usuario dentro del conjunto."""
    conjunto_id = current_user.conjunto_id

    if body.rol not in ROLES_VALIDOS:
        raise http_400(f"Rol inválido. Valores permitidos: {', '.join(ROLES_VALIDOS)}")

    uc = (
        db.query(UsuarioConjunto)
        .filter(
            UsuarioConjunto.usuario_id == usuario_id,
            UsuarioConjunto.conjunto_id == conjunto_id,
            UsuarioConjunto.is_deleted == False,  # noqa: E712
        )
        .first()
    )
    if not uc:
        raise http_404(ErrorMsg.NOT_FOUND)

    uc.rol = body.rol
    db.commit()
    db.refresh(uc)

    return UsuarioConjuntoOut(
        id=uc.id,
        usuario_id=uc.usuario_id,
        conjunto_id=uc.conjunto_id,
        rol=uc.rol,
        nombre=uc.usuario.nombre,
        correo=uc.usuario.correo,
        cedula=uc.usuario.cedula,
        telefono_ws=uc.usuario.telefono_ws,
        created_at=uc.created_at,
    )


@router.delete("/api/usuarios/{usuario_id}", status_code=204)
def remover_usuario(
    usuario_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("Administrador")),
):
    """Remueve un usuario del conjunto (soft delete del vínculo)."""
    conjunto_id = current_user.conjunto_id

    uc = (
        db.query(UsuarioConjunto)
        .filter(
            UsuarioConjunto.usuario_id == usuario_id,
            UsuarioConjunto.conjunto_id == conjunto_id,
            UsuarioConjunto.is_deleted == False,  # noqa: E712
        )
        .first()
    )
    if not uc:
        raise http_404(ErrorMsg.NOT_FOUND)

    uc.is_deleted = True
    uc.deleted_at = datetime.now(tz=BOGOTA_TZ)
    db.commit()


# ══════════════════════════════════════════════════════════════════════════════
# /api/configuracion — Administrador (editar) y Contador (solo lectura)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/api/configuracion", response_model=ConfiguracionOut)
def ver_configuracion(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("Administrador", "Contador")),
):
    config = _get_config_or_404(current_user.conjunto_id, db)
    return config


@router.put("/api/configuracion", response_model=ConfiguracionOut)
def editar_configuracion(
    body: ConfiguracionUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("Administrador")),
):
    config = _get_config_or_404(current_user.conjunto_id, db)

    if body.valor_cuota_estandar is not None:
        config.valor_cuota_estandar = body.valor_cuota_estandar
    if body.dia_notificacion_mora is not None:
        config.dia_notificacion_mora = body.dia_notificacion_mora
    if body.tasa_interes_mora is not None:
        config.tasa_interes_mora = body.tasa_interes_mora
    if body.permitir_interes is not None:
        config.permitir_interes = body.permitir_interes

    db.commit()
    db.refresh(config)
    return config


# ══════════════════════════════════════════════════════════════════════════════
# Helpers privados
# ══════════════════════════════════════════════════════════════════════════════

def _get_conjunto_or_404(conjunto_id: uuid.UUID, db: Session) -> Conjunto:
    c = (
        db.query(Conjunto)
        .filter(Conjunto.id == conjunto_id, Conjunto.is_deleted == False)  # noqa: E712
        .first()
    )
    if not c:
        raise http_404(ErrorMsg.CONJUNTO_NOT_FOUND)
    return c


def _get_config_or_404(conjunto_id: uuid.UUID, db: Session) -> ConfiguracionConjunto:
    config = (
        db.query(ConfiguracionConjunto)
        .filter(ConfiguracionConjunto.conjunto_id == conjunto_id)
        .first()
    )
    if not config:
        raise http_404("Configuración no encontrada para este conjunto")
    return config
