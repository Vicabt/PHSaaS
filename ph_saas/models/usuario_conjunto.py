"""
models/usuario_conjunto.py — Tabla: usuario_conjunto
Relación N:M entre usuario y conjunto con rol asignado.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import UUID, Boolean, DateTime, Enum, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ph_saas.models.base import Base

if TYPE_CHECKING:
    from ph_saas.models.usuario import Usuario
    from ph_saas.models.conjunto import Conjunto


class RolConjunto(str, enum.Enum):
    administrador = "Administrador"
    contador = "Contador"
    porteria = "Porteria"


class UsuarioConjunto(Base):
    __tablename__ = "usuario_conjunto"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuario.id"), nullable=False
    )
    conjunto_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conjunto.id"), nullable=False
    )
    rol: Mapped[str] = mapped_column(
        Enum("Administrador", "Contador", "Porteria", name="rol_conjunto_enum"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relaciones
    usuario: Mapped["Usuario"] = relationship("Usuario", back_populates="usuario_conjuntos")  # noqa: F821
    conjunto: Mapped["Conjunto"] = relationship("Conjunto", back_populates="usuario_conjuntos")  # noqa: F821

    # Índice parcial: evita duplicados activos (usuario en el mismo conjunto)
    __table_args__ = (
        Index(
            "uq_usuario_conjunto_activo",
            "usuario_id",
            "conjunto_id",
            unique=True,
            postgresql_where=(is_deleted == False),  # noqa: E712
        ),
    )
