"""
routers/pagos.py — Endpoints de Pagos y Saldos a Favor.

Rutas:
  GET    /api/pagos                        → AD, CO: lista pagos del conjunto
  POST   /api/pagos                        → AD, CO: registrar pago
  GET    /api/pagos/{id}                   → AD, CO: detalle con desglose
  DELETE /api/pagos/{id}                   → AD: anular pago (soft delete)
  GET    /api/saldos-a-favor               → AD, CO: lista saldos disponibles
  POST   /api/saldos-a-favor/{id}/aplicar  → AD, CO: aplicar saldo a favor a cuota
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from ph_saas.config import BOGOTA_TZ
from ph_saas.database import get_db
from ph_saas.dependencies import CurrentUser, require_role
from ph_saas.errors import ErrorMsg, http_404
from ph_saas.models.pago import Pago
from ph_saas.models.saldo_a_favor import SaldoAFavor
from ph_saas.schemas.pago import (
    AplicarSaldoRequest,
    PagoConDetalle,
    PagoCreate,
    PagoOut,
    SaldoAFavorOut,
)
from ph_saas.services.pago_service import anular_pago, aplicar_saldo_a_favor, registrar_pago

router = APIRouter(tags=["pagos"])


# ── Pagos ──────────────────────────────────────────────────────────────────────

@router.get("/api/pagos", response_model=list[PagoOut])
def listar_pagos(
    propiedad_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("Administrador", "Contador")),
):
    """Lista pagos activos del conjunto, opcionalmente filtrados por propiedad."""
    q = db.query(Pago).filter(
        Pago.conjunto_id == current_user.conjunto_id,
        Pago.is_deleted == False,  # noqa: E712
    )
    if propiedad_id:
        q = q.filter(Pago.propiedad_id == propiedad_id)
    return q.order_by(Pago.fecha_pago.desc(), Pago.created_at.desc()).all()


@router.post("/api/pagos", response_model=PagoConDetalle, status_code=201)
def crear_pago(
    body: PagoCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("Administrador", "Contador")),
):
    """Registra un pago con detalle por cuota."""
    pago = registrar_pago(db, current_user.conjunto_id, body)
    # Recargar con detalles para la respuesta
    return (
        db.query(Pago)
        .options(joinedload(Pago.detalles))
        .filter(Pago.id == pago.id)
        .first()
    )


@router.get("/api/pagos/{pago_id}", response_model=PagoConDetalle)
def detalle_pago(
    pago_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("Administrador", "Contador")),
):
    """Detalle de un pago con su desglose de cuotas."""
    pago = (
        db.query(Pago)
        .options(joinedload(Pago.detalles))
        .filter(
            Pago.id == pago_id,
            Pago.conjunto_id == current_user.conjunto_id,
            Pago.is_deleted == False,  # noqa: E712
        )
        .first()
    )
    if not pago:
        raise http_404(ErrorMsg.PAGO_NOT_FOUND)
    return pago


@router.delete("/api/pagos/{pago_id}", status_code=204)
def eliminar_pago(
    pago_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("Administrador")),
):
    """Anula (soft delete) un pago."""
    anular_pago(db, current_user.conjunto_id, pago_id)


# ── Saldos a favor ─────────────────────────────────────────────────────────────

@router.get("/api/saldos-a-favor", response_model=list[SaldoAFavorOut])
def listar_saldos_a_favor(
    propiedad_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("Administrador", "Contador")),
):
    """Lista saldos a favor disponibles del conjunto."""
    q = db.query(SaldoAFavor).filter(
        SaldoAFavor.conjunto_id == current_user.conjunto_id,
        SaldoAFavor.estado == "Disponible",
    )
    if propiedad_id:
        q = q.filter(SaldoAFavor.propiedad_id == propiedad_id)
    return q.order_by(SaldoAFavor.created_at.desc()).all()


@router.post("/api/saldos-a-favor/{saldo_id}/aplicar", response_model=SaldoAFavorOut)
def aplicar_saldo(
    saldo_id: uuid.UUID,
    body: AplicarSaldoRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("Administrador", "Contador")),
):
    """Aplica un saldo a favor a una cuota específica."""
    return aplicar_saldo_a_favor(db, current_user.conjunto_id, saldo_id, body.cuota_id)
