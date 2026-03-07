"""
models/pago.py — Tabla: pago
Encabezado del pago. Los detalles van en pago_detalle.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import UUID, Boolean, Date, DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ph_saas.models.base import Base


class Pago(Base):
    __tablename__ = "pago"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conjunto_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conjunto.id"), nullable=False
    )
    propiedad_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("propiedad.id"), nullable=False
    )
    fecha_pago: Mapped[date] = mapped_column(Date, nullable=False)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    metodo_pago: Mapped[str] = mapped_column(
        Enum("Efectivo", "Transferencia", "PSE", "Otro", name="metodo_pago_enum"),
        nullable=False,
    )
    referencia: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relaciones
    detalles: Mapped[list["PagoDetalle"]] = relationship("PagoDetalle", back_populates="pago")  # noqa: F821
    saldos_a_favor: Mapped[list["SaldoAFavor"]] = relationship("SaldoAFavor", back_populates="origen_pago")  # noqa: F821
