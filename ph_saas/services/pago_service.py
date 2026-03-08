"""
services/pago_service.py — Lógica de negocio para Pagos.

Contratos (ver RULES.md):
  - Imputación: primero interés, luego capital
  - Invariante: monto_aplicado = monto_a_interes + monto_a_capital
  - Movimiento contable por cada pago registrado
  - Saldo a favor cuando valor_total > suma(monto_aplicado)
  - Saldo: split atómico si excede deuda de cuota
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from ph_saas.config import BOGOTA_TZ
from ph_saas.errors import ErrorMsg, http_400, http_404
from ph_saas.models.cuota import Cuota
from ph_saas.models.movimiento_contable import MovimientoContable
from ph_saas.models.pago import Pago
from ph_saas.models.pago_detalle import PagoDetalle
from ph_saas.models.propiedad import Propiedad
from ph_saas.models.saldo_a_favor import SaldoAFavor
from ph_saas.schemas.pago import PagoCreate

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_saldo_pendiente(db: Session, cuota: Cuota) -> tuple[Decimal, Decimal]:
    """
    Retorna (interes_pendiente, capital_pendiente) de una cuota.
    interes_pendiente = interes_generado - suma(pago_detalle.monto_a_interes)
    capital_pendiente = valor_base - suma(pago_detalle.monto_a_capital)
    """
    row = (
        db.query(
            func.coalesce(func.sum(PagoDetalle.monto_a_interes), Decimal("0")),
            func.coalesce(func.sum(PagoDetalle.monto_a_capital), Decimal("0")),
        )
        .filter(PagoDetalle.cuota_id == cuota.id)
        .one()
    )
    interes_ya_pagado = row[0] or Decimal("0")
    capital_ya_pagado = row[1] or Decimal("0")

    interes_pendiente = cuota.interes_generado - interes_ya_pagado
    capital_pendiente = cuota.valor_base - capital_ya_pagado
    return interes_pendiente, capital_pendiente


def _imputar_abono(
    abono: Decimal,
    interes_pendiente: Decimal,
    capital_pendiente: Decimal,
) -> tuple[Decimal, Decimal]:
    """
    Imputa el abono siguiendo el orden legal colombiano: primero interés, luego capital.

    Retorna (monto_a_interes, monto_a_capital).
    Invariante garantizada: monto_a_interes + monto_a_capital == abono
    """
    if abono <= interes_pendiente:
        return abono, Decimal("0")
    else:
        monto_a_interes = interes_pendiente
        monto_a_capital = min(abono - interes_pendiente, capital_pendiente)
        return monto_a_interes, monto_a_capital


def _nuevo_estado_cuota(
    capital_pendiente: Decimal,
    interes_pendiente: Decimal,
    monto_a_capital: Decimal,
    monto_a_interes: Decimal,
) -> str | None:
    """
    Calcula el nuevo estado de la cuota después de aplicar el abono.
    Retorna None si el estado no debe cambiar (no debería ocurrir en la práctica).
    """
    capital_restante = capital_pendiente - monto_a_capital
    interes_restante = interes_pendiente - monto_a_interes

    if capital_restante <= Decimal("0") and interes_restante <= Decimal("0"):
        return "Pagada"
    else:
        return "Parcial"


# ── Registrar pago ─────────────────────────────────────────────────────────────

def registrar_pago(db: Session, conjunto_id: uuid.UUID, pago_in: PagoCreate) -> Pago:
    """
    Registra un pago con su detalle de cuotas.

    - Valida que la propiedad pertenezca al conjunto.
    - Valida que cada cuota pertenezca al conjunto y no esté Pagada.
    - Imputa monto: primero interés, luego capital.
    - Actualiza estado de cada cuota.
    - Crea movimiento contable Ingreso.
    - Si valor_total > suma(monto_aplicado): crea saldo_a_favor con el excedente.
    """
    # Validar propiedad
    propiedad = (
        db.query(Propiedad)
        .filter(
            Propiedad.id == pago_in.propiedad_id,
            Propiedad.conjunto_id == conjunto_id,
            Propiedad.is_deleted == False,  # noqa: E712
        )
        .first()
    )
    if not propiedad:
        raise http_404(ErrorMsg.PROPIEDAD_NOT_FOUND)

    # Validar valor_total
    if pago_in.valor_total <= Decimal("0"):
        raise http_400(ErrorMsg.PAGO_MONTO_INVALIDO)

    # Crear cabecera del pago
    pago = Pago(
        conjunto_id=conjunto_id,
        propiedad_id=pago_in.propiedad_id,
        fecha_pago=pago_in.fecha_pago,
        valor_total=pago_in.valor_total,
        metodo_pago=pago_in.metodo_pago,
        referencia=pago_in.referencia,
    )
    db.add(pago)
    db.flush()  # Obtener pago.id sin commit todavía

    total_aplicado = Decimal("0")

    for detalle_in in pago_in.detalles:
        # Validar cuota
        cuota = (
            db.query(Cuota)
            .filter(
                Cuota.id == detalle_in.cuota_id,
                Cuota.is_deleted == False,  # noqa: E712
            )
            .first()
        )
        if not cuota:
            raise http_404(ErrorMsg.CUOTA_NOT_FOUND)
        if cuota.conjunto_id != conjunto_id:
            raise http_400(ErrorMsg.PAGO_CUOTA_OTRO_CONJUNTO)
        if cuota.estado == "Pagada":
            raise http_400(ErrorMsg.CUOTA_YA_PAGADA)

        interes_pendiente, capital_pendiente = _get_saldo_pendiente(db, cuota)
        deuda_total = interes_pendiente + capital_pendiente

        abono = detalle_in.monto_aplicado
        if abono > deuda_total:
            raise http_400(ErrorMsg.PAGO_EXCEDE_DEUDA)

        monto_a_interes, monto_a_capital = _imputar_abono(abono, interes_pendiente, capital_pendiente)

        # Invariante: monto_aplicado = monto_a_interes + monto_a_capital
        detalle = PagoDetalle(
            pago_id=pago.id,
            cuota_id=cuota.id,
            monto_aplicado=abono,
            monto_a_interes=monto_a_interes,
            monto_a_capital=monto_a_capital,
        )
        db.add(detalle)
        total_aplicado += abono

        # Actualizar estado de la cuota
        nuevo_estado = _nuevo_estado_cuota(
            capital_pendiente, interes_pendiente, monto_a_capital, monto_a_interes
        )
        if nuevo_estado:
            cuota.estado = nuevo_estado

    # Movimiento contable — Ingreso por el pago
    movimiento = MovimientoContable(
        conjunto_id=conjunto_id,
        tipo="Ingreso",
        concepto=f"Pago registrado — {pago_in.metodo_pago}",
        referencia_tipo="PAGO",
        referencia_id=pago.id,
        monto=pago_in.valor_total,
        fecha=pago_in.fecha_pago,
    )
    db.add(movimiento)

    # Saldo a favor si hay excedente
    excedente = pago_in.valor_total - total_aplicado
    if excedente > Decimal("0"):
        saldo = SaldoAFavor(
            conjunto_id=conjunto_id,
            propiedad_id=pago_in.propiedad_id,
            monto=excedente,
            estado="Disponible",
            origen_pago_id=pago.id,
        )
        db.add(saldo)
        logger.info(f"[pago_service] Saldo a favor generado: {excedente} para propiedad {pago_in.propiedad_id}")

    db.commit()
    db.refresh(pago)
    logger.info(f"[pago_service] Pago registrado: {pago.id} — total {pago_in.valor_total}")
    return pago


# ── Anular pago ────────────────────────────────────────────────────────────────

def anular_pago(db: Session, conjunto_id: uuid.UUID, pago_id: uuid.UUID) -> None:
    """
    Soft delete de un pago. No revierte el estado de las cuotas afectadas
    (operación de auditoría — la reversión contable se hace manualmente).
    """
    pago = (
        db.query(Pago)
        .filter(
            Pago.id == pago_id,
            Pago.conjunto_id == conjunto_id,
            Pago.is_deleted == False,  # noqa: E712
        )
        .first()
    )
    if not pago:
        raise http_404(ErrorMsg.PAGO_NOT_FOUND)

    pago.is_deleted = True
    db.commit()
    logger.info(f"[pago_service] Pago anulado: {pago_id}")


# ── Aplicar saldo a favor ──────────────────────────────────────────────────────

def aplicar_saldo_a_favor(
    db: Session,
    conjunto_id: uuid.UUID,
    saldo_id: uuid.UUID,
    cuota_id: uuid.UUID,
) -> SaldoAFavor:
    """
    Aplica un saldo a favor a una cuota específica.

    Si el saldo supera la deuda de la cuota:
      1. Aplica el monto exacto → cuota pasa a Pagada.
      2. Crea nuevo saldo_a_favor con el excedente.
      3. Marca el original como Aplicado.
    Todo en una sola transacción atómica.
    """
    # Buscar saldo
    saldo = (
        db.query(SaldoAFavor)
        .filter(
            SaldoAFavor.id == saldo_id,
            SaldoAFavor.conjunto_id == conjunto_id,
        )
        .first()
    )
    if not saldo:
        raise http_404(ErrorMsg.SALDO_NOT_FOUND)
    if saldo.estado == "Aplicado":
        raise http_400(ErrorMsg.SALDO_YA_APLICADO)

    # Buscar cuota
    cuota = (
        db.query(Cuota)
        .filter(
            Cuota.id == cuota_id,
            Cuota.conjunto_id == conjunto_id,
            Cuota.is_deleted == False,  # noqa: E712
        )
        .first()
    )
    if not cuota:
        raise http_404(ErrorMsg.CUOTA_NOT_FOUND)
    if cuota.estado == "Pagada":
        raise http_400(ErrorMsg.CUOTA_YA_PAGADA)

    interes_pendiente, capital_pendiente = _get_saldo_pendiente(db, cuota)
    deuda_total = interes_pendiente + capital_pendiente

    if saldo.monto <= Decimal("0"):
        raise http_400(ErrorMsg.SALDO_INSUFICIENTE)

    monto_a_aplicar = min(saldo.monto, deuda_total)
    excedente = saldo.monto - monto_a_aplicar

    monto_a_interes, monto_a_capital = _imputar_abono(monto_a_aplicar, interes_pendiente, capital_pendiente)

    # Crear pago virtual para registrar la imputación
    pago_virtual = Pago(
        conjunto_id=conjunto_id,
        propiedad_id=cuota.propiedad_id,
        fecha_pago=datetime.now(tz=BOGOTA_TZ).date(),
        valor_total=monto_a_aplicar,
        metodo_pago="Otro",
        referencia=f"Saldo a favor aplicado — origen {saldo.origen_pago_id}",
    )
    db.add(pago_virtual)
    db.flush()

    detalle = PagoDetalle(
        pago_id=pago_virtual.id,
        cuota_id=cuota.id,
        monto_aplicado=monto_a_aplicar,
        monto_a_interes=monto_a_interes,
        monto_a_capital=monto_a_capital,
    )
    db.add(detalle)

    # Movimiento contable
    movimiento = MovimientoContable(
        conjunto_id=conjunto_id,
        tipo="Ingreso",
        concepto=f"Aplicación de saldo a favor — saldo {saldo_id}",
        referencia_tipo="PAGO",
        referencia_id=pago_virtual.id,
        monto=monto_a_aplicar,
        fecha=pago_virtual.fecha_pago,
    )
    db.add(movimiento)

    # Nuevo estado de la cuota
    nuevo_estado = _nuevo_estado_cuota(
        capital_pendiente, interes_pendiente, monto_a_capital, monto_a_interes
    )
    if nuevo_estado:
        cuota.estado = nuevo_estado

    # Marcar saldo original como Aplicado
    saldo.estado = "Aplicado"
    saldo.cuota_aplicada_id = cuota.id
    saldo.updated_at = datetime.now(tz=BOGOTA_TZ)

    # Crear saldo residual si hay excedente
    if excedente > Decimal("0"):
        nuevo_saldo = SaldoAFavor(
            conjunto_id=conjunto_id,
            propiedad_id=cuota.propiedad_id,
            monto=excedente,
            estado="Disponible",
            origen_pago_id=saldo.origen_pago_id,
        )
        db.add(nuevo_saldo)
        logger.info(f"[pago_service] Saldo residual creado: {excedente}")

    db.commit()
    db.refresh(saldo)
    logger.info(f"[pago_service] Saldo {saldo_id} aplicado a cuota {cuota_id}")
    return saldo
