"""
services/cartera_service.py — Lógica de negocio para Cartera.

Funciones:
  - get_resumen_cartera(db, conjunto_id)               → ResumenCartera
  - get_estado_cuenta(db, conjunto_id, propiedad_id)   → EstadoCuentaPropiedad | None
  - get_cartera_antiguedad(db, conjunto_id)             → list[CarteraAntiguedadItem]
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from ph_saas.models.cuota import Cuota
from ph_saas.models.pago_detalle import PagoDetalle
from ph_saas.models.propiedad import Propiedad
from ph_saas.models.saldo_a_favor import SaldoAFavor
from ph_saas.schemas.cartera import (
    CarteraAntiguedadItem,
    EstadoCuentaPropiedad,
    ResumenCartera,
)
from ph_saas.schemas.cuota import CuotaDetalle


# ── Helpers ────────────────────────────────────────────────────────────────────

def _calcular_saldo(
    db: Session, cuota: Cuota
) -> tuple[Decimal, Decimal, Decimal]:
    """
    Devuelve (total_capital_pagado, total_interes_pagado, saldo_pendiente).
    Saldo = (valor_base - capital_pagado) + (interes_generado - interes_pagado)
    """
    row = (
        db.query(
            func.coalesce(func.sum(PagoDetalle.monto_a_capital), Decimal("0")),
            func.coalesce(func.sum(PagoDetalle.monto_a_interes), Decimal("0")),
        )
        .filter(PagoDetalle.cuota_id == cuota.id)
        .one()
    )
    capital_pagado = row[0] or Decimal("0")
    interes_pagado = row[1] or Decimal("0")
    saldo = (cuota.valor_base - capital_pagado) + (cuota.interes_generado - interes_pagado)
    return capital_pagado, interes_pagado, max(saldo, Decimal("0"))


def _enrich_cuota(db: Session, cuota: Cuota) -> CuotaDetalle:
    """Enriquece una cuota con sus sumatorias calculadas."""
    capital_pagado, interes_pagado, saldo = _calcular_saldo(db, cuota)
    out = CuotaDetalle.model_validate(cuota)
    out.total_pagado_capital = capital_pagado
    out.total_pagado_interes = interes_pagado
    out.saldo_pendiente = saldo
    return out


# ── Servicios ──────────────────────────────────────────────────────────────────

def get_resumen_cartera(db: Session, conjunto_id: uuid.UUID) -> ResumenCartera:
    """Resumen de cartera del conjunto: conteos y totales agregados."""
    propiedades = (
        db.query(Propiedad)
        .filter(
            Propiedad.conjunto_id == conjunto_id,
            Propiedad.is_deleted == False,  # noqa: E712
        )
        .all()
    )

    propiedades_al_dia = 0
    propiedades_en_mora = 0
    total_deuda = Decimal("0")
    total_vencido = Decimal("0")
    total_interes_pendiente = Decimal("0")

    for propiedad in propiedades:
        cuotas_pendientes = (
            db.query(Cuota)
            .filter(
                Cuota.propiedad_id == propiedad.id,
                Cuota.conjunto_id == conjunto_id,
                Cuota.estado.in_(["Pendiente", "Parcial", "Vencida"]),
                Cuota.is_deleted == False,  # noqa: E712
            )
            .all()
        )

        if not cuotas_pendientes:
            propiedades_al_dia += 1
            continue

        tiene_mora = False
        for cuota in cuotas_pendientes:
            _, interes_pagado, saldo = _calcular_saldo(db, cuota)
            total_deuda += saldo
            interes_pend = max(cuota.interes_generado - interes_pagado, Decimal("0"))
            total_interes_pendiente += interes_pend
            if cuota.estado == "Vencida":
                total_vencido += saldo
                tiene_mora = True

        if tiene_mora:
            propiedades_en_mora += 1
        else:
            propiedades_al_dia += 1

    return ResumenCartera(
        total_propiedades=len(propiedades),
        propiedades_al_dia=propiedades_al_dia,
        propiedades_en_mora=propiedades_en_mora,
        total_deuda=total_deuda,
        total_vencido=total_vencido,
        total_interes_pendiente=total_interes_pendiente,
    )


def get_estado_cuenta(
    db: Session, conjunto_id: uuid.UUID, propiedad_id: uuid.UUID
) -> EstadoCuentaPropiedad | None:
    """
    Estado de cuenta completo de una propiedad.
    Retorna None si la propiedad no existe o no pertenece al conjunto.
    """
    propiedad = (
        db.query(Propiedad)
        .filter(
            Propiedad.id == propiedad_id,
            Propiedad.conjunto_id == conjunto_id,
            Propiedad.is_deleted == False,  # noqa: E712
        )
        .first()
    )
    if not propiedad:
        return None

    cuotas = (
        db.query(Cuota)
        .filter(
            Cuota.propiedad_id == propiedad_id,
            Cuota.conjunto_id == conjunto_id,
            Cuota.is_deleted == False,  # noqa: E712
        )
        .order_by(Cuota.periodo)
        .all()
    )

    cuotas_detalle = [_enrich_cuota(db, c) for c in cuotas]
    total_deuda = sum(
        (c.saldo_pendiente for c in cuotas_detalle if c.estado != "Pagada"),
        Decimal("0"),
    )

    saldo_a_favor_total = (
        db.query(func.coalesce(func.sum(SaldoAFavor.monto), Decimal("0")))
        .filter(
            SaldoAFavor.propiedad_id == propiedad_id,
            SaldoAFavor.conjunto_id == conjunto_id,
            SaldoAFavor.estado == "Disponible",
        )
        .scalar()
    ) or Decimal("0")

    return EstadoCuentaPropiedad(
        propiedad_id=propiedad_id,
        numero_apartamento=propiedad.numero_apartamento,
        conjunto_id=conjunto_id,
        cuotas=cuotas_detalle,
        saldo_a_favor_disponible=saldo_a_favor_total,
        total_deuda=total_deuda,
    )


def get_cartera_antiguedad(
    db: Session, conjunto_id: uuid.UUID
) -> list[CarteraAntiguedadItem]:
    """
    Clasifica propiedades con cuotas vencidas en rangos de antigüedad:
    0-30, 31-60, 61-90, 90+ días.
    Ordenado por días de mora descendente.
    """
    hoy = date.today()
    resultado: list[CarteraAntiguedadItem] = []

    propiedades = (
        db.query(Propiedad)
        .filter(
            Propiedad.conjunto_id == conjunto_id,
            Propiedad.is_deleted == False,  # noqa: E712
        )
        .all()
    )

    for propiedad in propiedades:
        cuotas_vencidas = (
            db.query(Cuota)
            .filter(
                Cuota.propiedad_id == propiedad.id,
                Cuota.conjunto_id == conjunto_id,
                Cuota.estado.in_(["Pendiente", "Parcial", "Vencida"]),
                Cuota.fecha_vencimiento < hoy,
                Cuota.is_deleted == False,  # noqa: E712
            )
            .all()
        )

        if not cuotas_vencidas:
            continue

        dias_max = max((hoy - c.fecha_vencimiento).days for c in cuotas_vencidas)
        saldo_total = sum(
            (_calcular_saldo(db, c)[2] for c in cuotas_vencidas),
            Decimal("0"),
        )

        if dias_max <= 30:
            rango = "0-30"
        elif dias_max <= 60:
            rango = "31-60"
        elif dias_max <= 90:
            rango = "61-90"
        else:
            rango = "90+"

        resultado.append(
            CarteraAntiguedadItem(
                propiedad_id=propiedad.id,
                numero_apartamento=propiedad.numero_apartamento,
                rango=rango,
                dias_mora_max=dias_max,
                saldo_total=saldo_total,
            )
        )

    resultado.sort(key=lambda x: x.dias_mora_max, reverse=True)
    return resultado
