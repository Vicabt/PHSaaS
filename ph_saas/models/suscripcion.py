"""
models/suscripcion.py — Tabla: suscripcion_saas
Un registro por conjunto. Controla el acceso SaaS.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import UUID, Date, DateTime, Enum, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ph_saas.models.base import Base


class SuscripcionSaaS(Base):
    __tablename__ = "suscripcion_saas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conjunto_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conjunto.id"), unique=True, nullable=False
    )
    estado: Mapped[str] = mapped_column(
        Enum("Activo", "Suspendido", name="estado_suscripcion_enum"), nullable=False
    )
    fecha_vencimiento: Mapped[date] = mapped_column(Date, nullable=False)
    valor_mensual: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relación
    conjunto: Mapped["Conjunto"] = relationship("Conjunto", back_populates="suscripcion")  # noqa: F821
