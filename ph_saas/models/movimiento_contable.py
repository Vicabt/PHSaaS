"""
models/movimiento_contable.py — Tabla: movimiento_contable
referencia_id es polimórfico — sin FK en BD. Validar en código que exista.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import UUID, Date, DateTime, Enum, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column
from ph_saas.models.base import Base


class MovimientoContable(Base):
    __tablename__ = "movimiento_contable"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conjunto_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    tipo: Mapped[str] = mapped_column(
        Enum("Ingreso", "Egreso", "Ajuste", name="tipo_movimiento_enum"), nullable=False
    )
    concepto: Mapped[str] = mapped_column(String(200), nullable=False)
    # referencia_tipo: 'PAGO', 'CUOTA', 'AJUSTE_MANUAL'
    referencia_tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    # Polimórfico — sin FK en BD. Validar en pago_service.py antes de insertar.
    referencia_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    monto: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_movimiento_ref", "referencia_tipo", "referencia_id"),
    )
