"""
schemas/configuracion.py — Schemas Pydantic para ConfiguracionConjunto.
"""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class ConfiguracionOut(BaseModel):
    valor_cuota_estandar: Decimal
    # dia_generacion_cuota oculto — NO se expone al cliente
    dia_notificacion_mora: int
    tasa_interes_mora: Decimal
    permitir_interes: bool

    model_config = {"from_attributes": True}


class ConfiguracionUpdate(BaseModel):
    valor_cuota_estandar: Optional[Decimal] = Field(None, gt=0)
    dia_notificacion_mora: Optional[int] = Field(None, ge=1, le=28)
    tasa_interes_mora: Optional[Decimal] = Field(None, ge=0)
    permitir_interes: Optional[bool] = None
