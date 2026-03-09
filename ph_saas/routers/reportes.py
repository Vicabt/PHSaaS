"""
routers/reportes.py — Endpoints de Reportes PDF.

Rutas:
  GET /api/reportes/estado-cuenta/{propiedad_id}  → AD, CO, PO: PDF estado de cuenta
  GET /api/reportes/paz-y-salvo/{propiedad_id}    → AD, CO, PO: PDF paz y salvo
  GET /api/reportes/cartera                       → AD, CO: PDF cartera general del conjunto
"""

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ph_saas.database import get_db
from ph_saas.dependencies import CurrentUser, require_role
from ph_saas.errors import ErrorMsg, http_404
from ph_saas.services.pdf_service import (
    generar_cartera_pdf,
    generar_estado_cuenta_pdf,
    generar_paz_y_salvo_pdf,
)

router = APIRouter(prefix="/api/reportes", tags=["reportes"])


@router.get("/estado-cuenta/{propiedad_id}")
def reporte_estado_cuenta(
    propiedad_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("Administrador", "Contador", "Porteria")),
):
    """Genera y retorna el PDF de estado de cuenta de una propiedad."""
    pdf = generar_estado_cuenta_pdf(db, current_user.conjunto_id, propiedad_id)
    if pdf is None:
        raise http_404(ErrorMsg.PROPIEDAD_NOT_FOUND)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=estado_cuenta_{propiedad_id}.pdf"
        },
    )


@router.get("/paz-y-salvo/{propiedad_id}")
def reporte_paz_y_salvo(
    propiedad_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("Administrador", "Contador", "Porteria")),
):
    """Genera y retorna el PDF de paz y salvo de una propiedad."""
    pdf = generar_paz_y_salvo_pdf(db, current_user.conjunto_id, propiedad_id)
    if pdf is None:
        raise http_404(ErrorMsg.PROPIEDAD_NOT_FOUND)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=paz_y_salvo_{propiedad_id}.pdf"
        },
    )


@router.get("/cartera")
def reporte_cartera(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_role("Administrador", "Contador")),
):
    """Genera y retorna el PDF de cartera general del conjunto."""
    pdf = generar_cartera_pdf(db, current_user.conjunto_id)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline; filename=cartera.pdf"},
    )
