"""
routers/cartera.py — Endpoints de Cartera.

Rutas:
  GET /api/cartera                        → AD, CO: resumen de cartera del conjunto
  GET /api/cartera/antiguedad             → AD, CO: clasificación por antigüedad (30/60/90/90+)
  GET /api/cartera/propiedad/{id}         → AD, CO, PO: estado de cuenta de una propiedad
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ph_saas.database import get_db
from ph_saas.dependencies import CurrentUser, require_role
from ph_saas.errors import ErrorMsg, http_404
from ph_saas.schemas.cartera import (
    CarteraAntiguedadItem,
    EstadoCuentaPropiedad,
    ResumenCartera,
)
from ph_saas.services.cartera_service import (
    get_cartera_antiguedad,
    get_estado_cuenta,
    get_resumen_cartera,
)

router = APIRouter(prefix="/api/cartera", tags=["cartera"])


@router.get("", response_model=ResumenCartera)
def resumen_cartera(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("Administrador", "Contador")),
):
    """Resumen de cartera del conjunto: totales y conteo de propiedades."""
    return get_resumen_cartera(db, current_user.conjunto_id)


@router.get("/antiguedad", response_model=list[CarteraAntiguedadItem])
def cartera_antiguedad(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("Administrador", "Contador")),
):
    """Clasifica propiedades en mora por rangos de antigüedad: 0-30, 31-60, 61-90, 90+."""
    return get_cartera_antiguedad(db, current_user.conjunto_id)


@router.get("/propiedad/{propiedad_id}", response_model=EstadoCuentaPropiedad)
def estado_cuenta_propiedad(
    propiedad_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("Administrador", "Contador", "Porteria")),
):
    """Estado de cuenta completo de una propiedad con todas sus cuotas y saldos."""
    estado = get_estado_cuenta(db, current_user.conjunto_id, propiedad_id)
    if not estado:
        raise http_404(ErrorMsg.PROPIEDAD_NOT_FOUND)
    return estado
