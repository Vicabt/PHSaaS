"""
routers/internal.py — Endpoints internos protegidos por X-Internal-Token.

Rutas:
  POST /internal/generar-cuotas      → invocado por cron-job.org el día 1 de cada mes
  POST /internal/calcular-intereses  → invocado por cron-job.org el día 5 de cada mes

Seguridad: todos los endpoints requieren header X-Internal-Token.
La validación se hace como dependencia compartida (no por endpoint individual).
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from ph_saas.config import BOGOTA_TZ, settings
from ph_saas.database import get_db
from ph_saas.errors import ErrorMsg, http_401
from ph_saas.models.conjunto import Conjunto
from ph_saas.services.cuota_service import calcular_intereses, generar_cuotas
from ph_saas.services.whatsapp_service import (
    notificar_cuotas_generadas,
    notificar_mora_conjunto,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])


# ── Dependencia de autenticación interna ───────────────────────────────────────

def verify_internal_token(x_internal_token: str = Header(...)):
    """Verifica que el header X-Internal-Token coincida con INTERNAL_TOKEN en config."""
    if x_internal_token != settings.INTERNAL_TOKEN:
        logger.warning("[internal] Intento de acceso con token inválido")
        raise http_401(ErrorMsg.INTERNAL_TOKEN_INVALIDO)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/generar-cuotas")
def generar_cuotas_todos(
    periodo: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """
    Genera cuotas para TODOS los conjuntos activos en el periodo indicado.
    Idempotente: conjuntos que ya tienen cuotas generadas se omiten silenciosamente.

    Parámetro: ?periodo=YYYY-MM (query string)
    """
    conjuntos = (
        db.query(Conjunto)
        .filter(Conjunto.is_deleted == False)  # noqa: E712
        .all()
    )

    resultados = []
    for conjunto in conjuntos:
        try:
            cuotas = generar_cuotas(db, conjunto.id, periodo)
            mensajes_enviados = notificar_cuotas_generadas(db, conjunto.id, cuotas, conjunto.nombre)
            resultados.append({
                "conjunto_id": str(conjunto.id),
                "nombre": conjunto.nombre,
                "cuotas_generadas": len(cuotas),
                "notificaciones_enviadas": mensajes_enviados,
            })
        except ValueError as e:
            logger.error(f"[internal] Error generando cuotas para {conjunto.id}: {e}")
            resultados.append({
                "conjunto_id": str(conjunto.id),
                "nombre": conjunto.nombre,
                "error": str(e),
            })

    logger.info(f"[internal] generar-cuotas completado para periodo {periodo}: {len(resultados)} conjuntos")
    return {"periodo": periodo, "resultados": resultados}


@router.post("/calcular-intereses")
def calcular_intereses_todos(
    db: Session = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """
    Calcula intereses de mora para TODOS los conjuntos que tengan permitir_interes=True.
    Idempotente: cuotas ya procesadas en este mes se omiten.

    El mes de ejecución se determina automáticamente (mes actual en Bogotá).
    """
    mes_ejecucion = datetime.now(tz=BOGOTA_TZ).strftime("%Y-%m")

    conjuntos = (
        db.query(Conjunto)
        .filter(Conjunto.is_deleted == False)  # noqa: E712
        .all()
    )

    resultados = []
    for conjunto in conjuntos:
        try:
            procesadas = calcular_intereses(db, conjunto.id, mes_ejecucion)
            resultados.append({
                "conjunto_id": str(conjunto.id),
                "nombre": conjunto.nombre,
                "cuotas_procesadas": procesadas,
            })
        except Exception as e:
            logger.error(f"[internal] Error calculando intereses para {conjunto.id}: {e}")
            resultados.append({
                "conjunto_id": str(conjunto.id),
                "nombre": conjunto.nombre,
                "error": str(e),
            })

    logger.info(f"[internal] calcular-intereses completado, mes {mes_ejecucion}: {len(resultados)} conjuntos")
    return {"mes_ejecucion": mes_ejecucion, "resultados": resultados}


@router.post("/notificar-mora")
def notificar_mora_todos(
    db: Session = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """
    Envia recordatorio de mora via WhatsApp a propietarios con cuotas vencidas.
    Debe invocarse desde cron-job.org el dia configurable de cada mes.
    Itera todos los conjuntos activos.
    """
    conjuntos = (
        db.query(Conjunto)
        .filter(Conjunto.is_deleted == False)  # noqa: E712
        .all()
    )

    resultados = []
    for conjunto in conjuntos:
        try:
            enviados = notificar_mora_conjunto(db, conjunto.id, conjunto.nombre)
            resultados.append({
                "conjunto_id": str(conjunto.id),
                "nombre": conjunto.nombre,
                "notificaciones_enviadas": enviados,
            })
        except Exception as e:
            logger.error(f"[internal] Error notificando mora para {conjunto.id}: {e}")
            resultados.append({
                "conjunto_id": str(conjunto.id),
                "nombre": conjunto.nombre,
                "error": str(e),
            })

    logger.info(f"[internal] notificar-mora completado: {len(resultados)} conjuntos procesados")
    return {"resultados": resultados}
