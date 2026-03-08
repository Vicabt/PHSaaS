"""
routers/cuotas.py — Endpoints de Cuotas.

Rutas:
  GET  /api/cuotas                     → AD, CO: lista cuotas (filtros: periodo, estado, propiedad_id)
  POST /api/cuotas/generar             → AD: generación manual de cuotas para un periodo
  GET  /api/cuotas/{id}                → AD, CO: detalle de cuota
  GET  /api/cuotas/propiedad/{id}      → AD, CO, PO: cuotas de una propiedad
"""

import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ph_saas.database import get_db
from ph_saas.dependencies import CurrentUser, require_role
from ph_saas.errors import ErrorMsg, http_400, http_404
from ph_saas.models.cuota import Cuota
from ph_saas.models.pago_detalle import PagoDetalle
from ph_saas.models.propiedad import Propiedad
from ph_saas.schemas.cuota import CuotaDetalle, CuotaGenerarRequest, CuotaOut
from ph_saas.services.cuota_service import generar_cuotas

router = APIRouter(prefix="/api/cuotas", tags=["cuotas"])


def _enrich(db: Session, cuota: Cuota) -> CuotaDetalle:
    """Agrega totales calculados al modelo de cuota."""
    row = (
        db.query(
            func.coalesce(func.sum(PagoDetalle.monto_a_capital), Decimal("0")),
            func.coalesce(func.sum(PagoDetalle.monto_a_interes), Decimal("0")),
        )
        .filter(PagoDetalle.cuota_id == cuota.id)
        .one()
    )
    total_capital = row[0] or Decimal("0")
    total_interes = row[1] or Decimal("0")
    saldo = (cuota.valor_base - total_capital) + (cuota.interes_generado - total_interes)

    out = CuotaDetalle.model_validate(cuota)
    out.total_pagado_capital = total_capital
    out.total_pagado_interes = total_interes
    out.saldo_pendiente = max(saldo, Decimal("0"))
    return out


@router.get("", response_model=list[CuotaOut])
def listar_cuotas(
    periodo: Optional[str] = Query(None, description="Filtro YYYY-MM"),
    estado: Optional[str] = Query(None, description="Pendiente | Parcial | Pagada | Vencida"),
    propiedad_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("Administrador", "Contador")),
):
    q = db.query(Cuota).filter(
        Cuota.conjunto_id == current_user.conjunto_id,
        Cuota.is_deleted == False,  # noqa: E712
    )
    if periodo:
        q = q.filter(Cuota.periodo == periodo)
    if estado:
        q = q.filter(Cuota.estado == estado)
    if propiedad_id:
        q = q.filter(Cuota.propiedad_id == propiedad_id)
    return q.order_by(Cuota.periodo.desc(), Cuota.created_at).all()


@router.post("/generar", response_model=list[CuotaOut], status_code=201)
def generar_cuotas_manual(
    body: CuotaGenerarRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("Administrador")),
):
    """Genera cuotas para todas las propiedades activas del conjunto en el periodo indicado."""
    try:
        cuotas = generar_cuotas(db, current_user.conjunto_id, body.periodo)
    except ValueError as e:
        raise http_400(str(e))

    if not cuotas:
        raise http_400(ErrorMsg.CUOTA_YA_GENERADA)

    return cuotas


@router.get("/propiedad/{propiedad_id}", response_model=list[CuotaDetalle])
def cuotas_por_propiedad(
    propiedad_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("Administrador", "Contador", "Porteria")),
):
    """Retorna todas las cuotas activas de una propiedad, enriquecidas con saldos."""
    # Verificar que la propiedad pertenezca al conjunto
    propiedad = (
        db.query(Propiedad)
        .filter(
            Propiedad.id == propiedad_id,
            Propiedad.conjunto_id == current_user.conjunto_id,
            Propiedad.is_deleted == False,  # noqa: E712
        )
        .first()
    )
    if not propiedad:
        raise http_404(ErrorMsg.PROPIEDAD_NOT_FOUND)

    cuotas = (
        db.query(Cuota)
        .filter(
            Cuota.propiedad_id == propiedad_id,
            Cuota.conjunto_id == current_user.conjunto_id,
            Cuota.is_deleted == False,  # noqa: E712
        )
        .order_by(Cuota.periodo.desc())
        .all()
    )
    return [_enrich(db, c) for c in cuotas]


@router.get("/{cuota_id}", response_model=CuotaDetalle)
def detalle_cuota(
    cuota_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("Administrador", "Contador")),
):
    cuota = (
        db.query(Cuota)
        .filter(
            Cuota.id == cuota_id,
            Cuota.conjunto_id == current_user.conjunto_id,
            Cuota.is_deleted == False,  # noqa: E712
        )
        .first()
    )
    if not cuota:
        raise http_404(ErrorMsg.CUOTA_NOT_FOUND)
    return _enrich(db, cuota)
