"""
models/propiedad.py — Tabla: propiedad
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import UUID, Boolean, DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ph_saas.models.base import Base

if TYPE_CHECKING:
    from ph_saas.models.conjunto import Conjunto
    from ph_saas.models.usuario import Usuario
    from ph_saas.models.cuota import Cuota


class Propiedad(Base):
    __tablename__ = "propiedad"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conjunto_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conjunto.id"), nullable=False
    )
    propietario_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuario.id"), nullable=True
    )
    numero_apartamento: Mapped[str] = mapped_column(String(20), nullable=False)
    estado: Mapped[str] = mapped_column(
        Enum("Activo", "Inactivo", name="estado_propiedad_enum"),
        nullable=False,
        default="Activo",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relaciones
    conjunto: Mapped["Conjunto"] = relationship("Conjunto", back_populates="propiedades")  # noqa: F821
    propietario: Mapped["Usuario | None"] = relationship("Usuario")  # noqa: F821
    cuotas: Mapped[list["Cuota"]] = relationship("Cuota", back_populates="propiedad")  # noqa: F821

    # Índice parcial: evita duplicados activos de número de apartamento en el conjunto
    __table_args__ = (
        Index(
            "uq_propiedad_activa",
            "conjunto_id",
            "numero_apartamento",
            unique=True,
            postgresql_where=(is_deleted == False),  # noqa: E712
        ),
    )
