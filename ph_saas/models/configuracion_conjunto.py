"""
models/configuracion_conjunto.py — Tabla: configuracion_conjunto
Una fila por conjunto. PK = conjunto_id.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import UUID, Boolean, DateTime, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ph_saas.models.base import Base


class ConfiguracionConjunto(Base):
    __tablename__ = "configuracion_conjunto"

    conjunto_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conjunto.id"), primary_key=True
    )
    valor_cuota_estandar: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # OCULTO en UI — reservado para fase futura (cron dinámico)
    dia_generacion_cuota: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Etiqueta en UI: "Día de envío de recordatorio por WhatsApp"
    dia_notificacion_mora: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    # Porcentaje mensual, ej. 2.00 = 2% mensual
    tasa_interes_mora: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    permitir_interes: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relación
    conjunto: Mapped["Conjunto"] = relationship("Conjunto")  # noqa: F821
