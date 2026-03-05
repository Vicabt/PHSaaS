"""
models/conjunto.py — Tabla: conjunto
"""

import uuid
from datetime import datetime
from sqlalchemy import UUID, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ph_saas.models.base import Base


class Conjunto(Base):
    __tablename__ = "conjunto"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    nombre: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    nit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    direccion: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ciudad: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relaciones
    propiedades: Mapped[list["Propiedad"]] = relationship(  # noqa: F821
        "Propiedad", back_populates="conjunto"
    )
    suscripcion: Mapped["SuscripcionSaaS"] = relationship(  # noqa: F821
        "SuscripcionSaaS", back_populates="conjunto", uselist=False
    )
    usuario_conjuntos: Mapped[list["UsuarioConjunto"]] = relationship(  # noqa: F821
        "UsuarioConjunto", back_populates="conjunto"
    )
