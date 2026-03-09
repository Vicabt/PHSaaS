"""
schemas/cartera.py — Schemas Pydantic para Cartera y Estado de Cuenta.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel

from ph_saas.schemas.cuota import CuotaDetalle


class ResumenCartera(BaseModel):
    """Resumen de cartera del conjunto."""
    total_propiedades: int
    propiedades_al_dia: int
    propiedades_en_mora: int
    total_deuda: Decimal               # saldo pendiente de todas las cuotas no pagadas
    total_vencido: Decimal             # solo cuotas en estado Vencida
    total_interes_pendiente: Decimal   # interés acumulado sin pagar


class EstadoCuentaPropiedad(BaseModel):
    """Estado de cuenta completo de una propiedad."""
    propiedad_id: uuid.UUID
    numero_apartamento: str
    conjunto_id: uuid.UUID
    cuotas: list[CuotaDetalle]
    saldo_a_favor_disponible: Decimal
    total_deuda: Decimal


class CarteraAntiguedadItem(BaseModel):
    """Una fila de la tabla de antigüedad de cartera."""
    propiedad_id: uuid.UUID
    numero_apartamento: str
    rango: str          # "0-30", "31-60", "61-90", "90+"
    dias_mora_max: int  # días del vencimiento más antiguo sin pagar
    saldo_total: Decimal
