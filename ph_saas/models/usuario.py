"""
models/usuario.py — Tabla: usuario
El id es el mismo UUID de Supabase Auth.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import UUID, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ph_saas.models.base import Base


class Usuario(Base):
    __tablename__ = "usuario"

    # UUID idéntico al de Supabase Auth (auth.users.id)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    cedula: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    correo: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    telefono_ws: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relaciones
    usuario_conjuntos: Mapped[list["UsuarioConjunto"]] = relationship(  # noqa: F821
        "UsuarioConjunto", back_populates="usuario"
    )
