"""
models/cuota_interes_log.py — Tabla: cuota_interes_log
Idempotencia para CALCULO_INTERESES: si existe (cuota_id, mes_ejecucion) → no ejecutar.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import UUID, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ph_saas.models.base import Base


class CuotaInteresLog(Base):
    __tablename__ = "cuota_interes_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cuota_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cuota.id"), nullable=False
    )
    conjunto_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conjunto.id"), nullable=False
    )
    # Mes en que corrió el job — formato YYYY-MM (no el periodo de la cuota)
    mes_ejecucion: Mapped[str] = mapped_column(String(7), nullable=False)
    # Interés sumado en este mes
    monto_aplicado: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    # valor_base - suma(pago_detalle.monto_a_capital) al momento del cálculo
    saldo_capital: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relación
    cuota: Mapped["Cuota"] = relationship("Cuota", back_populates="interes_logs")  # noqa: F821

    __table_args__ = (
        UniqueConstraint("cuota_id", "mes_ejecucion", name="uq_cuota_interes_log"),
    )
