"""
services/cuota_service.py — Lógica de negocio para Cuotas.

Contratos (ver RULES.md):
  - generar_cuotas: idempotente via proceso_log (GENERACION_CUOTAS)
  - calcular_intereses: idempotente via cuota_interes_log (cuota_id, mes_ejecucion)
  - marcar_cuotas_vencidas: job diario APScheduler — llamado por scheduler.py
"""
from __future__ import annotations

import re
import uuid
import logging
from datetime import date, datetime
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from ph_saas.config import BOGOTA_TZ
from ph_saas.models.configuracion_conjunto import ConfiguracionConjunto
from ph_saas.models.cuota import Cuota
from ph_saas.models.cuota_interes_log import CuotaInteresLog
from ph_saas.models.pago_detalle import PagoDetalle
from ph_saas.models.proceso_log import ProcesoLog
from ph_saas.models.propiedad import Propiedad

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _ultimo_dia_mes(year: int, month: int) -> date:
    """Devuelve el último día del mes indicado."""
    return date(year, month, 1) + relativedelta(months=1) - relativedelta(days=1)


def _validar_periodo(periodo: str) -> tuple[int, int]:
    """Valida formato YYYY-MM y devuelve (year, month)."""
    if not re.match(r"^\d{4}-\d{2}$", periodo):
        raise ValueError("El formato del periodo debe ser YYYY-MM")
    year, month = int(periodo[:4]), int(periodo[5:])
    if not (1 <= month <= 12):
        raise ValueError("Mes inválido en periodo")
    return year, month


# ── Generación de cuotas ───────────────────────────────────────────────────────

def generar_cuotas(db: Session, conjunto_id: uuid.UUID, periodo: str) -> list[Cuota]:
    """
    Genera cuotas para todas las propiedades activas del conjunto en el periodo dado.

    Idempotente: si ya existe un proceso_log para (conjunto_id, GENERACION_CUOTAS, periodo)
    no hace nada y devuelve lista vacía.

    Retorna la lista de cuotas generadas (puede ser vacía si ya existían).
    """
    year, month = _validar_periodo(periodo)

    # Idempotencia — verificar proceso_log
    ya_ejecutado = (
        db.query(ProcesoLog)
        .filter(
            ProcesoLog.conjunto_id == conjunto_id,
            ProcesoLog.tipo_proceso == "GENERACION_CUOTAS",
            ProcesoLog.periodo == periodo,
        )
        .first()
    )
    if ya_ejecutado:
        logger.info(f"[cuota_service] Cuotas periodo {periodo} ya generadas para conjunto {conjunto_id}")
        return []

    # Configuración del conjunto (necesitamos valor_cuota_estandar)
    config = (
        db.query(ConfiguracionConjunto)
        .filter(ConfiguracionConjunto.conjunto_id == conjunto_id)
        .first()
    )
    if not config:
        raise ValueError(f"El conjunto {conjunto_id} no tiene configuración. Configure valor_cuota_estandar primero.")

    # Propiedades activas
    propiedades = (
        db.query(Propiedad)
        .filter(
            Propiedad.conjunto_id == conjunto_id,
            Propiedad.estado == "Activo",
            Propiedad.is_deleted == False,  # noqa: E712
        )
        .all()
    )

    fecha_vencimiento = _ultimo_dia_mes(year, month)
    cuotas_creadas: list[Cuota] = []

    for propiedad in propiedades:
        # Verificar si ya existe cuota activa para esta propiedad en este periodo
        ya_existe = (
            db.query(Cuota)
            .filter(
                Cuota.conjunto_id == conjunto_id,
                Cuota.propiedad_id == propiedad.id,
                Cuota.periodo == periodo,
                Cuota.is_deleted == False,  # noqa: E712
            )
            .first()
        )
        if ya_existe:
            continue

        cuota = Cuota(
            conjunto_id=conjunto_id,
            propiedad_id=propiedad.id,
            periodo=periodo,
            valor_base=config.valor_cuota_estandar,
            interes_generado=Decimal("0.00"),
            estado="Pendiente",
            fecha_vencimiento=fecha_vencimiento,
        )
        db.add(cuota)
        cuotas_creadas.append(cuota)

    # Registrar en proceso_log (idempotencia futura)
    log = ProcesoLog(
        conjunto_id=conjunto_id,
        tipo_proceso="GENERACION_CUOTAS",
        periodo=periodo,
        ejecutado_en=datetime.now(tz=BOGOTA_TZ),
    )
    db.add(log)
    db.commit()

    for c in cuotas_creadas:
        db.refresh(c)

    logger.info(f"[cuota_service] Generadas {len(cuotas_creadas)} cuotas para periodo {periodo}, conjunto {conjunto_id}")
    return cuotas_creadas


# ── Cálculo de intereses ───────────────────────────────────────────────────────

def calcular_intereses(db: Session, conjunto_id: uuid.UUID, mes_ejecucion: str) -> int:
    """
    Calcula y aplica interés de mora a cuotas vencidas del conjunto.

    Solo aplica si configuracion_conjunto.permitir_interes = True.
    Idempotente via cuota_interes_log(cuota_id, mes_ejecucion).
    Retorna el número de cuotas procesadas.
    """
    _validar_periodo(mes_ejecucion)

    config = (
        db.query(ConfiguracionConjunto)
        .filter(ConfiguracionConjunto.conjunto_id == conjunto_id)
        .first()
    )
    if not config or not config.permitir_interes:
        logger.info(f"[cuota_service] Intereses desactivados para conjunto {conjunto_id}")
        return 0

    tasa = config.tasa_interes_mora  # porcentaje mensual, ej. 2.00 = 2%
    hoy = date.today()

    # Cuotas candidatas: vencidas y con saldo pendiente
    cuotas = (
        db.query(Cuota)
        .filter(
            Cuota.conjunto_id == conjunto_id,
            Cuota.fecha_vencimiento < hoy,
            Cuota.estado.in_(["Pendiente", "Parcial", "Vencida"]),
            Cuota.is_deleted == False,  # noqa: E712
        )
        .all()
    )

    procesadas = 0
    for cuota in cuotas:
        # Idempotencia: verificar si ya se calculó para este mes
        ya_calculado = (
            db.query(CuotaInteresLog)
            .filter(
                CuotaInteresLog.cuota_id == cuota.id,
                CuotaInteresLog.mes_ejecucion == mes_ejecucion,
            )
            .first()
        )
        if ya_calculado:
            continue

        # Saldo de capital = valor_base - suma(pago_detalle.monto_a_capital)
        total_capital_pagado = (
            db.query(func.coalesce(func.sum(PagoDetalle.monto_a_capital), Decimal("0")))
            .filter(PagoDetalle.cuota_id == cuota.id)
            .scalar()
        ) or Decimal("0")

        saldo_capital = cuota.valor_base - total_capital_pagado
        if saldo_capital <= Decimal("0"):
            continue

        interes_mes = saldo_capital * (tasa / Decimal("100"))
        interes_mes = interes_mes.quantize(Decimal("0.01"))

        # Acumular en cuota — NUNCA sobreescribir
        cuota.interes_generado = cuota.interes_generado + interes_mes

        # Registrar en log (idempotencia)
        log = CuotaInteresLog(
            cuota_id=cuota.id,
            conjunto_id=conjunto_id,
            mes_ejecucion=mes_ejecucion,
            monto_aplicado=interes_mes,
            saldo_capital=saldo_capital,
        )
        db.add(log)
        procesadas += 1

    db.commit()
    logger.info(f"[cuota_service] Intereses calculados para {procesadas} cuotas, mes {mes_ejecucion}, conjunto {conjunto_id}")
    return procesadas


# ── Marcar cuotas Vencidas (APScheduler diario) ────────────────────────────────

def marcar_cuotas_vencidas(db: Session) -> int:
    """
    Marca como 'Vencida' todas las cuotas con fecha_vencimiento < hoy
    en estado 'Pendiente' o 'Parcial' en TODOS los conjuntos.

    Llamado por APScheduler a medianoche (Bogotá). No filtra por conjunto_id.
    Retorna el número de cuotas actualizadas.
    """
    hoy = date.today()

    cuotas = (
        db.query(Cuota)
        .filter(
            Cuota.fecha_vencimiento < hoy,
            Cuota.estado.in_(["Pendiente", "Parcial"]),
            Cuota.is_deleted == False,  # noqa: E712
        )
        .all()
    )

    for cuota in cuotas:
        cuota.estado = "Vencida"

    db.commit()
    logger.info(f"[cuota_service] Cuotas marcadas como Vencida: {len(cuotas)}")
    return len(cuotas)
