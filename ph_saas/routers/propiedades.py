"""
routers/propiedades.py — CRUD de Propiedades por conjunto.

Rutas:
  GET    /api/propiedades          → AD, CO: lista propiedades del conjunto
  POST   /api/propiedades          → AD: crear propiedad
  GET    /api/propiedades/{id}     → AD, CO, PO: detalle
  PUT    /api/propiedades/{id}     → AD: editar
  DELETE /api/propiedades/{id}     → AD: soft delete
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ph_saas.database import get_db
from ph_saas.dependencies import CurrentUser, require_role
from ph_saas.errors import ErrorMsg, http_404, http_409
from ph_saas.models.propiedad import Propiedad
from ph_saas.models.usuario import Usuario
from ph_saas.schemas.propiedad import PropiedadCreate, PropiedadDetalle, PropiedadOut, PropiedadUpdate

router = APIRouter(prefix="/api/propiedades", tags=["propiedades"])

ESTADOS_VALIDOS = {"Activo", "Inactivo"}


@router.get("", response_model=list[PropiedadOut])
def listar_propiedades(
    estado: Optional[str] = Query(None, description="Activo | Inactivo"),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("Administrador", "Contador")),
):
    """Lista propiedades activas del conjunto. Filtra por estado si se indica."""
    q = (
        db.query(Propiedad)
        .filter(
            Propiedad.conjunto_id == current_user.conjunto_id,
            Propiedad.is_deleted == False,  # noqa: E712
        )
    )
    if estado:
        q = q.filter(Propiedad.estado == estado)
    return q.order_by(Propiedad.numero_apartamento).all()


@router.post("", response_model=PropiedadOut, status_code=201)
def crear_propiedad(
    body: PropiedadCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("Administrador")),
):
    """Crea una propiedad en el conjunto activo."""
    conjunto_id = current_user.conjunto_id

    if body.estado not in ESTADOS_VALIDOS:
        from ph_saas.errors import http_400
        raise http_400(f"Estado inválido. Valores permitidos: {', '.join(ESTADOS_VALIDOS)}")

    # Verificar duplicado de número en el conjunto (índice parcial, pero validamos primero)
    existe = (
        db.query(Propiedad)
        .filter(
            Propiedad.conjunto_id == conjunto_id,
            Propiedad.numero_apartamento == body.numero_apartamento,
            Propiedad.is_deleted == False,  # noqa: E712
        )
        .first()
    )
    if existe:
        raise http_409(ErrorMsg.PROPIEDAD_DUPLICATE)

    # Verificar que el propietario exista si se indica
    if body.propietario_id:
        propietario = (
            db.query(Usuario)
            .filter(Usuario.id == body.propietario_id, Usuario.is_deleted == False)  # noqa: E712
            .first()
        )
        if not propietario:
            raise http_404("Propietario no encontrado")

    propiedad = Propiedad(
        conjunto_id=conjunto_id,
        numero_apartamento=body.numero_apartamento,
        propietario_id=body.propietario_id,
        estado=body.estado,
    )
    db.add(propiedad)
    db.commit()
    db.refresh(propiedad)
    return propiedad


@router.get("/{propiedad_id}", response_model=PropiedadDetalle)
def obtener_propiedad(
    propiedad_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("Administrador", "Contador", "Porteria")),
):
    """Detalle de una propiedad con datos del propietario."""
    propiedad = _get_propiedad_or_404(propiedad_id, current_user.conjunto_id, db)

    return PropiedadDetalle(
        id=propiedad.id,
        conjunto_id=propiedad.conjunto_id,
        numero_apartamento=propiedad.numero_apartamento,
        estado=propiedad.estado,
        propietario_id=propiedad.propietario_id,
        created_at=propiedad.created_at,
        propietario_nombre=propiedad.propietario.nombre if propiedad.propietario else None,
        propietario_correo=propiedad.propietario.correo if propiedad.propietario else None,
    )


@router.put("/{propiedad_id}", response_model=PropiedadOut)
def editar_propiedad(
    propiedad_id: uuid.UUID,
    body: PropiedadUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("Administrador")),
):
    propiedad = _get_propiedad_or_404(propiedad_id, current_user.conjunto_id, db)

    if body.numero_apartamento and body.numero_apartamento != propiedad.numero_apartamento:
        existe = (
            db.query(Propiedad)
            .filter(
                Propiedad.conjunto_id == current_user.conjunto_id,
                Propiedad.numero_apartamento == body.numero_apartamento,
                Propiedad.is_deleted == False,  # noqa: E712
            )
            .first()
        )
        if existe:
            raise http_409(ErrorMsg.PROPIEDAD_DUPLICATE)
        propiedad.numero_apartamento = body.numero_apartamento

    if body.estado is not None:
        if body.estado not in ESTADOS_VALIDOS:
            from ph_saas.errors import http_400
            raise http_400(f"Estado inválido. Valores permitidos: {', '.join(ESTADOS_VALIDOS)}")
        propiedad.estado = body.estado

    if body.propietario_id is not None:
        # Permitir desasignar propietario enviando null explícito
        if body.propietario_id == uuid.UUID("00000000-0000-0000-0000-000000000000"):
            propiedad.propietario_id = None
        else:
            propietario = (
                db.query(Usuario)
                .filter(Usuario.id == body.propietario_id, Usuario.is_deleted == False)  # noqa: E712
                .first()
            )
            if not propietario:
                raise http_404("Propietario no encontrado")
            propiedad.propietario_id = body.propietario_id

    db.commit()
    db.refresh(propiedad)
    return propiedad


@router.delete("/{propiedad_id}", status_code=204)
def eliminar_propiedad(
    propiedad_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("Administrador")),
):
    propiedad = _get_propiedad_or_404(propiedad_id, current_user.conjunto_id, db)
    propiedad.is_deleted = True
    db.commit()


# ── Helper privado ─────────────────────────────────────────────────────────────

def _get_propiedad_or_404(propiedad_id: uuid.UUID, conjunto_id: uuid.UUID, db: Session) -> Propiedad:
    p = (
        db.query(Propiedad)
        .filter(
            Propiedad.id == propiedad_id,
            Propiedad.conjunto_id == conjunto_id,
            Propiedad.is_deleted == False,  # noqa: E712
        )
        .first()
    )
    if not p:
        raise http_404(ErrorMsg.PROPIEDAD_NOT_FOUND)
    return p
