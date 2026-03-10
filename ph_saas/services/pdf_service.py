"""
services/pdf_service.py — Generación de PDFs con WeasyPrint.

Funciones:
  - generar_estado_cuenta_pdf(db, conjunto_id, propiedad_id) → bytes | None
  - generar_paz_y_salvo_pdf(db, conjunto_id, propiedad_id)   → bytes | None
  - generar_cartera_pdf(db, conjunto_id)                     → bytes
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session

from ph_saas.models.conjunto import Conjunto
from ph_saas.services.cartera_service import (
    get_cartera_antiguedad,
    get_estado_cuenta,
    get_resumen_cartera,
)


def _get_jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader("ph_saas/templates/pdf"),
        autoescape=True,
    )


def _fmt_cop(valor: Decimal | None) -> str:
    """Formatea un valor Decimal como moneda COP."""
    if valor is None:
        return "$ 0"
    return f"$ {valor:,.0f}".replace(",", ".")


def _render_pdf(html_str: str) -> bytes:
    """Convierte HTML a bytes PDF usando xhtml2pdf (sin deps nativas de OS)."""
    import io
    from xhtml2pdf import pisa
    dest = io.BytesIO()
    pisa.CreatePDF(io.StringIO(html_str), dest=dest, encoding="utf-8")
    return dest.getvalue()


def generar_estado_cuenta_pdf(
    db: Session, conjunto_id: uuid.UUID, propiedad_id: uuid.UUID
) -> bytes | None:
    """
    Genera el PDF del estado de cuenta de una propiedad.
    Retorna None si la propiedad no existe o no pertenece al conjunto.
    """
    estado = get_estado_cuenta(db, conjunto_id, propiedad_id)
    if not estado:
        return None

    conjunto = db.query(Conjunto).filter(Conjunto.id == conjunto_id).first()
    conjunto_nombre = conjunto.nombre if conjunto else ""

    env = _get_jinja_env()
    tmpl = env.get_template("estado_cuenta.html")
    html_str = tmpl.render(
        estado=estado,
        conjunto_nombre=conjunto_nombre,
        fecha_generacion=date.today().strftime("%d/%m/%Y"),
        fmt_cop=_fmt_cop,
    )
    return _render_pdf(html_str)


def generar_paz_y_salvo_pdf(
    db: Session, conjunto_id: uuid.UUID, propiedad_id: uuid.UUID
) -> bytes | None:
    """
    Genera el PDF de paz y salvo de una propiedad.
    Retorna None si la propiedad no existe o no pertenece al conjunto.
    """
    estado = get_estado_cuenta(db, conjunto_id, propiedad_id)
    if not estado:
        return None

    conjunto = db.query(Conjunto).filter(Conjunto.id == conjunto_id).first()
    conjunto_nombre = conjunto.nombre if conjunto else ""

    al_dia = estado.total_deuda == Decimal("0")

    env = _get_jinja_env()
    tmpl = env.get_template("paz_y_salvo.html")
    html_str = tmpl.render(
        estado=estado,
        conjunto_nombre=conjunto_nombre,
        al_dia=al_dia,
        fecha_generacion=date.today().strftime("%d/%m/%Y"),
        fmt_cop=_fmt_cop,
    )
    return _render_pdf(html_str)


def generar_cartera_pdf(db: Session, conjunto_id: uuid.UUID) -> bytes:
    """
    Genera el PDF de resumen de cartera del conjunto con tabla de antigüedad.
    """
    resumen = get_resumen_cartera(db, conjunto_id)
    antiguedad = get_cartera_antiguedad(db, conjunto_id)

    conjunto = db.query(Conjunto).filter(Conjunto.id == conjunto_id).first()
    conjunto_nombre = conjunto.nombre if conjunto else ""

    env = _get_jinja_env()
    tmpl = env.get_template("cartera.html")
    html_str = tmpl.render(
        resumen=resumen,
        antiguedad=antiguedad,
        conjunto_nombre=conjunto_nombre,
        fecha_generacion=date.today().strftime("%d/%m/%Y"),
        fmt_cop=_fmt_cop,
    )
    return _render_pdf(html_str)
