"""
models/proceso_log.py — Tabla: proceso_log
Solo para idempotencia de GENERACION_CUOTAS.
Los intereses usan cuota_interes_log, NO esta tabla.
"""

import uuid
from datetime import datetime
from sqlalchemy import UUID, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ph_saas.models.base import Base


class ProcesoLog(Base):
    __tablename__ = "proceso_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conjunto_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conjunto.id"), nullable=False
    )
    # Solo 'GENERACION_CUOTAS'
    tipo_proceso: Mapped[str] = mapped_column(String(50), nullable=False)
    # Formato YYYY-MM — NUNCA un UUID aquí
    periodo: Mapped[str] = mapped_column(String(7), nullable=False)
    ejecutado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("conjunto_id", "tipo_proceso", "periodo", name="uq_proceso_log"),
    )
