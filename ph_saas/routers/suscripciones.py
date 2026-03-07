"""
routers/suscripciones.py — Gestión de suscripciones SaaS.

Rutas:
  GET  /admin/suscripciones                           → SA: lista todas las suscripciones
  PUT  /admin/suscripciones/{conjunto_id}/pagar       → SA: registra pago, extiende un mes
  PUT  /admin/suscripciones/{conjunto_id}/suspender   → SA: suspende acceso
  PUT  /admin/suscripciones/{conjunto_id}/activar     → SA: reactiva acceso
  GET  /api/suscripcion/mi-vencimiento                → AD: fecha de vencimiento (solo lectura)
"""

import uuid
from datetime import date
from dateutil.relativedelta import relativedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ph_saas.database import get_db
from ph_saas.dependencies import CurrentUser, require_role, require_superadmin
from ph_saas.errors import ErrorMsg, http_404, http_400
from ph_saas.models.suscripcion import SuscripcionSaaS
from ph_saas.schemas.conjunto import SuscripcionOut, SuscripcionPagarBody, SuscripcionSuspenderBody

router = APIRouter(tags=["suscripciones"])


@router.get("/admin/suscripciones", response_model=list[SuscripcionOut])
def listar_suscripciones(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_superadmin),
):
    """Lista todas las suscripciones SaaS ordenadas por estado y vencimiento."""
    return (
        db.query(SuscripcionSaaS)
        .order_by(SuscripcionSaaS.estado, SuscripcionSaaS.fecha_vencimiento)
        .all()
    )


@router.put("/admin/suscripciones/{conjunto_id}/pagar", response_model=SuscripcionOut)
def registrar_pago_suscripcion(
    conjunto_id: uuid.UUID,
    body: SuscripcionPagarBody,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_superadmin),
):
    """
    Registra el pago mensual: extiende la fecha_vencimiento un mes
    y activa la suscripción si estaba suspendida.
    """
    sus = _get_suscripcion_or_404(conjunto_id, db)

    # Extender desde hoy si ya venció, o desde la fecha de vencimiento actual
    base = max(sus.fecha_vencimiento, date.today())
    sus.fecha_vencimiento = base + relativedelta(months=1)
    sus.estado = "Activo"

    if body.observaciones:
        sus.observaciones = body.observaciones

    db.commit()
    db.refresh(sus)
    return sus


@router.put("/admin/suscripciones/{conjunto_id}/suspender", response_model=SuscripcionOut)
def suspender_suscripcion(
    conjunto_id: uuid.UUID,
    body: SuscripcionSuspenderBody,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_superadmin),
):
    sus = _get_suscripcion_or_404(conjunto_id, db)

    if sus.estado == "Suspendido":
        raise http_400(ErrorMsg.SUSCRIPCION_YA_SUSPENDIDA)

    sus.estado = "Suspendido"
    if body.observaciones:
        sus.observaciones = body.observaciones

    db.commit()
    db.refresh(sus)
    return sus


@router.put("/admin/suscripciones/{conjunto_id}/activar", response_model=SuscripcionOut)
def activar_suscripcion(
    conjunto_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_superadmin),
):
    sus = _get_suscripcion_or_404(conjunto_id, db)

    if sus.estado == "Activo":
        raise http_400(ErrorMsg.SUSCRIPCION_YA_ACTIVA)

    sus.estado = "Activo"
    db.commit()
    db.refresh(sus)
    return sus


@router.get("/api/suscripcion/mi-vencimiento")
def ver_mi_vencimiento(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("Administrador")),
):
    """Retorna la fecha de vencimiento de la suscripción del conjunto activo (solo lectura)."""
    sus = _get_suscripcion_or_404(current_user.conjunto_id, db)
    return {
        "data": {
            "estado": sus.estado,
            "fecha_vencimiento": sus.fecha_vencimiento.isoformat(),
        },
        "message": "ok",
    }


# ── Helper privado ─────────────────────────────────────────────────────────────

def _get_suscripcion_or_404(conjunto_id: uuid.UUID, db: Session) -> SuscripcionSaaS:
    sus = (
        db.query(SuscripcionSaaS)
        .filter(SuscripcionSaaS.conjunto_id == conjunto_id)
        .first()
    )
    if not sus:
        raise http_404(ErrorMsg.SUSCRIPCION_NOT_FOUND)
    return sus
