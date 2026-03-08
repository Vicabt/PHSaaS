"""
schemas/cuota.py — Schemas Pydantic para Cuota.
"""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, field_validator


class CuotaOut(BaseModel):
    id: uuid.UUID
    conjunto_id: uuid.UUID
    propiedad_id: uuid.UUID
    periodo: str
    valor_base: Decimal
    interes_generado: Decimal
    estado: str
    fecha_vencimiento: date
    created_at: datetime

    model_config = {"from_attributes": True}


class CuotaDetalle(CuotaOut):
    """CuotaOut + sumatorias calculadas al vuelo."""
    total_pagado_capital: Optional[Decimal] = None
    total_pagado_interes: Optional[Decimal] = None
    saldo_pendiente: Optional[Decimal] = None


class CuotaGenerarRequest(BaseModel):
    periodo: str  # formato YYYY-MM

    @field_validator("periodo")
    @classmethod
    def validar_periodo(cls, v: str) -> str:
        if not re.match(r"^\d{4}-\d{2}$", v):
            raise ValueError("El formato del periodo debe ser YYYY-MM")
        return v
