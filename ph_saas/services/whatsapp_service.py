"""
services/whatsapp_service.py — Notificaciones WhatsApp via Twilio.

Diseño:
  - El cliente Twilio se crea de forma lazy solo si TWILIO_ACCOUNT_SID está configurado.
  - Si las credenciales no están presentes, todas las funciones NO fallan: loguean y retornan.
  - Cualquier error del envío también se captura para no interrumpir el flujo principal.
  - Formato de teléfono: la BD almacena el número (ej. "+573001234567" o "3001234567").
    Se normaliza agregando el prefijo "whatsapp:" requerido por Twilio.

Funciones públicas:
  - notificar_cuotas_generadas(db, conjunto_id, cuotas)  → después de generar cuotas
  - notificar_mora_conjunto(db, conjunto_id)              → recordatorio de mora
  - notificar_confirmacion_pago(telefono, conjunto_nombre, numero_apt, valor, fecha)
  - notificar_paz_y_salvo(telefono, conjunto_nombre, numero_apt)
"""
from __future__ import annotations

import logging
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from ph_saas.config import settings
from ph_saas.models.configuracion_conjunto import ConfiguracionConjunto
from ph_saas.models.cuota import Cuota
from ph_saas.models.pago_detalle import PagoDetalle
from ph_saas.models.propiedad import Propiedad
from ph_saas.models.usuario import Usuario

logger = logging.getLogger(__name__)


# ── Cliente Twilio (lazy) ──────────────────────────────────────────────────────

def _get_twilio_client():
    """
    Retorna el cliente Twilio si las credenciales están configuradas, None en caso contrario.
    No lanza excepciones — la ausencia de credenciales es un estado válido en desarrollo.
    """
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        return None
    try:
        from twilio.rest import Client  # noqa: PLC0415
        return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    except Exception as exc:
        logger.warning(f"[whatsapp] No se pudo crear cliente Twilio: {exc}")
        return None


def _fmt_ws(telefono: str | None) -> str | None:
    """
    Formatea el número de teléfono al formato WhatsApp de Twilio: "whatsapp:+XXXXXXXXXXX".
    Retorna None si el teléfono es vacío o None.
    """
    if not telefono:
        return None
    telefono = telefono.strip()
    if not telefono:
        return None
    # Si ya tiene el prefijo completo whatsapp:, retornar tal cual
    if telefono.startswith("whatsapp:"):
        return telefono
    # Agregar + si falta (Colombia: 57XXXXXXXXXX)
    if not telefono.startswith("+"):
        telefono = "+" + telefono
    return "whatsapp:" + telefono


def _enviar(telefono_ws: str | None, body: str) -> bool:
    """
    Envía el mensaje de WhatsApp. Retorna True si se envió, False en cualquier otro caso.
    Nunca lanza excepciones hacia el caller.
    """
    if not telefono_ws:
        logger.debug("[whatsapp] Telefono no configurado, mensaje omitido")
        return False

    client = _get_twilio_client()
    if client is None:
        logger.info("[whatsapp] Twilio no configurado (TWILIO_ACCOUNT_SID vacío), mensaje omitido")
        return False

    try:
        message = client.messages.create(
            from_=settings.TWILIO_WHATSAPP_FROM,
            to=telefono_ws,
            body=body,
        )
        logger.info(f"[whatsapp] Mensaje enviado SID={message.sid} -> {telefono_ws}")
        return True
    except Exception as exc:
        logger.error(f"[whatsapp] Error al enviar mensaje a {telefono_ws}: {exc}")
        return False


# ── Helpers de formato ─────────────────────────────────────────────────────────

def _fmt_cop(valor: Decimal | None) -> str:
    if valor is None:
        return "$0"
    return f"${valor:,.0f}".replace(",", ".")


def _get_propietario_tel(db: Session, propiedad: Propiedad) -> str | None:
    """Retorna el telefono_ws formateado del propietario de la propiedad, o None."""
    if not propiedad.propietario_id:
        return None
    usuario = db.query(Usuario).filter(Usuario.id == propiedad.propietario_id).first()
    if not usuario:
        return None
    return _fmt_ws(usuario.telefono_ws)


# ── Notificaciones públicas ────────────────────────────────────────────────────

def notificar_cuotas_generadas(
    db: Session,
    conjunto_id: uuid.UUID,
    cuotas: list[Cuota],
    conjunto_nombre: str,
) -> int:
    """
    Envía una notificación de cuota generada al propietario de cada propiedad.
    Retorna el número de mensajes enviados con éxito.
    """
    if not cuotas:
        return 0

    enviados = 0
    for cuota in cuotas:
        propiedad = (
            db.query(Propiedad)
            .filter(Propiedad.id == cuota.propiedad_id)
            .first()
        )
        if not propiedad:
            continue

        tel = _get_propietario_tel(db, propiedad)
        if not tel:
            continue

        body = (
            f"*{conjunto_nombre}*\n"
            f"Se ha generado su cuota de administracion:\n"
            f"- Apartamento: {propiedad.numero_apartamento}\n"
            f"- Periodo: {cuota.periodo}\n"
            f"- Valor: {_fmt_cop(cuota.valor_base)}\n"
            f"- Vencimiento: {cuota.fecha_vencimiento.strftime('%d/%m/%Y')}\n"
            f"Por favor realice su pago antes de la fecha de vencimiento."
        )
        if _enviar(tel, body):
            enviados += 1

    logger.info(f"[whatsapp] notificar_cuotas_generadas: {enviados}/{len(cuotas)} mensajes enviados")
    return enviados


def notificar_mora_conjunto(
    db: Session,
    conjunto_id: uuid.UUID,
    conjunto_nombre: str,
) -> int:
    """
    Envia recordatorio de mora a todas las propiedades con cuotas vencidas no pagadas.
    Agrupa todas las cuotas vencidas por propiedad en un solo mensaje.
    Retorna el número de mensajes enviados.
    """
    # Propiedades con cuotas vencidas (Vencida, Parcial con fecha pasada)
    hoy = date.today()
    cuotas_mora = (
        db.query(Cuota)
        .filter(
            Cuota.conjunto_id == conjunto_id,
            Cuota.estado.in_(["Vencida", "Parcial", "Pendiente"]),
            Cuota.fecha_vencimiento < hoy,
            Cuota.is_deleted == False,  # noqa: E712
        )
        .order_by(Cuota.propiedad_id, Cuota.periodo)
        .all()
    )

    if not cuotas_mora:
        return 0

    # Calcular saldo pendiente por cuota y agrupar por propiedad
    from collections import defaultdict
    por_propiedad: dict[uuid.UUID, list[tuple[Cuota, Decimal]]] = defaultdict(list)

    for cuota in cuotas_mora:
        row = (
            db.query(func.coalesce(func.sum(PagoDetalle.monto_aplicado), Decimal("0")))
            .filter(PagoDetalle.cuota_id == cuota.id)
            .scalar()
        )
        ya_pagado = row or Decimal("0")
        saldo = cuota.valor_base + cuota.interes_generado - ya_pagado
        if saldo > Decimal("0"):
            por_propiedad[cuota.propiedad_id].append((cuota, saldo))

    enviados = 0
    for propiedad_id, items in por_propiedad.items():
        propiedad = db.query(Propiedad).filter(Propiedad.id == propiedad_id).first()
        if not propiedad:
            continue

        tel = _get_propietario_tel(db, propiedad)
        if not tel:
            continue

        total_deuda = sum(s for _, s in items)
        periodos = ", ".join(c.periodo for c, _ in items)

        body = (
            f"*{conjunto_nombre}* - Aviso de mora\n"
            f"Apreciado propietario del apartamento {propiedad.numero_apartamento}:\n"
            f"Tiene {len(items)} cuota(s) pendiente(s) de pago: {periodos}\n"
            f"Total adeudado: {_fmt_cop(total_deuda)}\n"
            f"Por favor regularice su situacion a la mayor brevedad."
        )
        if _enviar(tel, body):
            enviados += 1

    logger.info(f"[whatsapp] notificar_mora_conjunto: {enviados} mensajes enviados para conjunto {conjunto_id}")
    return enviados


def notificar_confirmacion_pago(
    telefono_ws: str | None,
    conjunto_nombre: str,
    numero_apartamento: str,
    valor: Decimal,
    fecha: date,
) -> bool:
    """
    Envía confirmación de pago al propietario.
    Retorna True si el mensaje fue enviado.
    """
    tel = _fmt_ws(telefono_ws)
    body = (
        f"*{conjunto_nombre}*\n"
        f"Confirmacion de pago recibido:\n"
        f"- Apartamento: {numero_apartamento}\n"
        f"- Valor: {_fmt_cop(valor)}\n"
        f"- Fecha: {fecha.strftime('%d/%m/%Y')}\n"
        f"Gracias por su pago."
    )
    return _enviar(tel, body)


def notificar_paz_y_salvo(
    telefono_ws: str | None,
    conjunto_nombre: str,
    numero_apartamento: str,
) -> bool:
    """
    Envía notificacion de paz y salvo al propietario.
    Retorna True si el mensaje fue enviado.
    """
    tel = _fmt_ws(telefono_ws)
    body = (
        f"*{conjunto_nombre}*\n"
        f"Certificado de paz y salvo generado.\n"
        f"Apartamento {numero_apartamento} se encuentra al dia con sus obligaciones.\n"
        f"Puede descargar el certificado desde el portal."
    )
    return _enviar(tel, body)
