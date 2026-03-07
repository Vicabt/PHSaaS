"""
schemas/usuario.py — Schemas Pydantic para Usuario y UsuarioConjunto.
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ── Usuario ────────────────────────────────────────────────────────────────────

class UsuarioCreate(BaseModel):
    """
    Crea un usuario en Supabase Auth + registro en tabla usuario.
    El SuperAdmin / Administrador usa este schema al invitar a alguien.
    """
    nombre: str = Field(..., max_length=100)
    correo: EmailStr
    password: str = Field(..., min_length=8)
    cedula: Optional[str] = Field(None, max_length=20)
    telefono_ws: Optional[str] = Field(None, max_length=20)
    rol: str = Field(..., description="Administrador | Contador | Porteria")


class UsuarioUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=100)
    cedula: Optional[str] = Field(None, max_length=20)
    telefono_ws: Optional[str] = Field(None, max_length=20)


class UsuarioOut(BaseModel):
    id: uuid.UUID
    nombre: str
    correo: str
    cedula: Optional[str]
    telefono_ws: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── UsuarioConjunto ───────────────────────────────────────────────────────────

class UsuarioConjuntoOut(BaseModel):
    id: uuid.UUID
    usuario_id: uuid.UUID
    conjunto_id: uuid.UUID
    rol: str
    nombre: str
    correo: str
    cedula: Optional[str]
    telefono_ws: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class CambiarRolBody(BaseModel):
    rol: str = Field(..., description="Administrador | Contador | Porteria")
