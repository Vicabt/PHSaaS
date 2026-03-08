"""
schemas/pago.py — Schemas Pydantic para Pago, PagoDetalle y SaldoAFavor.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, field_validator


# ── Entrada ────────────────────────────────────────────────────────────────────

class PagoDetalleIn(BaseModel):
    """Un renglón del pago: qué cuota se abona y cuánto."""
    cuota_id: uuid.UUID
    monto_aplicado: Decimal

    @field_validator("monto_aplicado")
    @classmethod
    def monto_positivo(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0"):
            raise ValueError("El monto aplicado debe ser mayor a cero")
        return v


class PagoCreate(BaseModel):
    propiedad_id: uuid.UUID
    fecha_pago: date
    valor_total: Decimal
    metodo_pago: str               # Efectivo | Transferencia | PSE | Otro
    referencia: Optional[str] = None
    detalles: list[PagoDetalleIn]  # Al menos un renglón

    @field_validator("valor_total")
    @classmethod
    def valor_positivo(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0"):
            raise ValueError("El valor total debe ser mayor a cero")
        return v

    @field_validator("metodo_pago")
    @classmethod
    def metodo_valido(cls, v: str) -> str:
        validos = {"Efectivo", "Transferencia", "PSE", "Otro"}
        if v not in validos:
            raise ValueError(f"Método de pago inválido. Opciones: {', '.join(sorted(validos))}")
        return v

    @field_validator("detalles")
    @classmethod
    def al_menos_un_detalle(cls, v: list) -> list:
        if not v:
            raise ValueError("Se requiere al menos un detalle de cuota")
        return v


class AplicarSaldoRequest(BaseModel):
    cuota_id: uuid.UUID


# ── Salida ─────────────────────────────────────────────────────────────────────

class PagoDetalleOut(BaseModel):
    id: uuid.UUID
    pago_id: uuid.UUID
    cuota_id: uuid.UUID
    monto_aplicado: Decimal
    monto_a_interes: Decimal
    monto_a_capital: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


class PagoOut(BaseModel):
    id: uuid.UUID
    conjunto_id: uuid.UUID
    propiedad_id: uuid.UUID
    fecha_pago: date
    valor_total: Decimal
    metodo_pago: str
    referencia: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class PagoConDetalle(PagoOut):
    detalles: list[PagoDetalleOut] = []


class SaldoAFavorOut(BaseModel):
    id: uuid.UUID
    conjunto_id: uuid.UUID
    propiedad_id: uuid.UUID
    monto: Decimal
    estado: str
    origen_pago_id: uuid.UUID
    cuota_aplicada_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
