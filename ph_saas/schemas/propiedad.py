"""
schemas/propiedad.py — Schemas Pydantic para Propiedad.
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Propiedad ──────────────────────────────────────────────────────────────────

class PropiedadCreate(BaseModel):
    numero_apartamento: str = Field(..., max_length=20)
    propietario_id: Optional[uuid.UUID] = None
    estado: str = "Activo"


class PropiedadUpdate(BaseModel):
    numero_apartamento: Optional[str] = Field(None, max_length=20)
    propietario_id: Optional[uuid.UUID] = None
    estado: Optional[str] = None


class PropiedadOut(BaseModel):
    id: uuid.UUID
    conjunto_id: uuid.UUID
    numero_apartamento: str
    estado: str
    propietario_id: Optional[uuid.UUID]
    created_at: datetime

    model_config = {"from_attributes": True}


class PropiedadDetalle(PropiedadOut):
    """Propiedad con datos del propietario."""
    propietario_nombre: Optional[str] = None
    propietario_correo: Optional[str] = None

    model_config = {"from_attributes": True}
