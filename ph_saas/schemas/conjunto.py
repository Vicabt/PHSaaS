"""
schemas/conjunto.py — Schemas Pydantic para Conjunto y Suscripción SaaS.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


# ── Conjunto ───────────────────────────────────────────────────────────────────

class ConjuntoCreate(BaseModel):
    nombre: str = Field(..., max_length=100)
    nit: Optional[str] = Field(None, max_length=20)
    direccion: Optional[str] = Field(None, max_length=200)
    ciudad: Optional[str] = Field(None, max_length=100)
    suscripcion: Optional["SuscripcionCreate"] = None


class ConjuntoUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=100)
    nit: Optional[str] = Field(None, max_length=20)
    direccion: Optional[str] = Field(None, max_length=200)
    ciudad: Optional[str] = Field(None, max_length=100)


class ConjuntoOut(BaseModel):
    id: uuid.UUID
    nombre: str
    nit: Optional[str]
    direccion: Optional[str]
    ciudad: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class ConjuntoDetalle(ConjuntoOut):
    """Conjunto con suscripción incluida."""
    suscripcion: Optional["SuscripcionOut"] = None

    model_config = {"from_attributes": True}


# ── Suscripción SaaS ───────────────────────────────────────────────────────────

class SuscripcionCreate(BaseModel):
    """Al crear un conjunto se puede incluir la suscripción inicial."""
    estado: str = "Activo"
    fecha_vencimiento: date
    valor_mensual: Decimal = Field(..., gt=0)
    observaciones: Optional[str] = None


class SuscripcionOut(BaseModel):
    id: uuid.UUID
    conjunto_id: uuid.UUID
    estado: str
    fecha_vencimiento: date
    valor_mensual: Decimal
    observaciones: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SuscripcionPagarBody(BaseModel):
    """Body para registrar pago y extender un mes."""
    observaciones: Optional[str] = None


class SuscripcionSuspenderBody(BaseModel):
    observaciones: Optional[str] = None


# Actualizar forward refs
ConjuntoCreate.model_rebuild()
ConjuntoDetalle.model_rebuild()
