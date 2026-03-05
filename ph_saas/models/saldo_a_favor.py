"""
models/saldo_a_favor.py — Tabla: saldo_a_favor
Se genera cuando pago.valor_total > suma(pago_detalle.monto_aplicado).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import UUID, DateTime, Enum, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ph_saas.models.base import Base


class SaldoAFavor(Base):
    __tablename__ = "saldo_a_favor"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conjunto_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conjunto.id"), nullable=False
    )
    propiedad_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("propiedad.id"), nullable=False
    )
    monto: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    estado: Mapped[str] = mapped_column(
        Enum("Disponible", "Aplicado", name="estado_saldo_enum"),
        nullable=False,
        default="Disponible",
    )
    # Pago que originó este saldo
    origen_pago_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pago.id"), nullable=False
    )
    # Cuota a la que se aplicó (solo cuando estado = 'Aplicado')
    cuota_aplicada_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cuota.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relaciones
    origen_pago: Mapped["Pago"] = relationship("Pago", back_populates="saldos_a_favor")  # noqa: F821
    cuota_aplicada: Mapped["Cuota | None"] = relationship("Cuota")  # noqa: F821
