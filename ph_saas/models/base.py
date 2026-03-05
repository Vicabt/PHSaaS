"""
models/base.py — Base declarativa compartida por todos los modelos SQLAlchemy.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
