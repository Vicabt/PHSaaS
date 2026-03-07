"""
models/pago_detalle.py — Tabla: pago_detalle
Invariante obligatoria: monto_aplicado = monto_a_interes + monto_a_capital
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import UUID, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ph_saas.models.base import Base


class PagoDetalle(Base):
    __tablename__ = "pago_detalle"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pago_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pago.id"), nullable=False
    )
    cuota_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cuota.id"), nullable=False
    )
    # Invariante: monto_aplicado = monto_a_interes + monto_a_capital
    monto_aplicado: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    monto_a_interes: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    monto_a_capital: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relaciones
    pago: Mapped["Pago"] = relationship("Pago", back_populates="detalles")  # noqa: F821
    cuota: Mapped["Cuota"] = relationship("Cuota", back_populates="pagos_detalle")  # noqa: F821
