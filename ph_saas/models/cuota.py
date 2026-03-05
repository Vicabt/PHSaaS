"""
models/cuota.py — Tabla: cuota
interes_generado es acumulativo — NUNCA sobreescribir, solo sumar.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import UUID, Boolean, Date, DateTime, Enum, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ph_saas.models.base import Base


class Cuota(Base):
    __tablename__ = "cuota"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conjunto_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conjunto.id"), nullable=False
    )
    propiedad_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("propiedad.id"), nullable=False
    )
    # Formato YYYY-MM
    periodo: Mapped[str] = mapped_column(String(7), nullable=False)
    valor_base: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    # Acumulativo — nunca sobreescribir, solo sumar con +=
    interes_generado: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0.00"), nullable=False
    )
    estado: Mapped[str] = mapped_column(
        Enum("Pendiente", "Parcial", "Pagada", "Vencida", name="estado_cuota_enum"),
        nullable=False,
        default="Pendiente",
    )
    # Último día del mes del periodo
    fecha_vencimiento: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relaciones
    propiedad: Mapped["Propiedad"] = relationship("Propiedad", back_populates="cuotas")  # noqa: F821
    pagos_detalle: Mapped[list["PagoDetalle"]] = relationship("PagoDetalle", back_populates="cuota")  # noqa: F821
    interes_logs: Mapped[list["CuotaInteresLog"]] = relationship("CuotaInteresLog", back_populates="cuota")  # noqa: F821

    # Índice parcial: una sola cuota activa por propiedad y periodo
    __table_args__ = (
        Index(
            "uq_cuota_activa",
            "conjunto_id",
            "propiedad_id",
            "periodo",
            unique=True,
            postgresql_where=(is_deleted == False),  # noqa: E712
        ),
    )
