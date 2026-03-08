"""
scheduler.py — APScheduler para jobs automáticos.
Job diario a medianoche (America/Bogota) → marca cuotas como Vencida.
Los triggers de generación de cuotas y cálculo de intereses van por cron-job.org.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="America/Bogota")


def _marcar_cuotas_vencidas():
    """
    Job diario, medianoche Bogotá.
    Marca como 'Vencida' todas las cuotas con fecha_vencimiento < hoy
    en estado 'Pendiente' o 'Parcial'.

    Implementación completa en Fase 2 — cuota_service.marcar_cuotas_vencidas().
    """
    logger.info("[scheduler] Iniciando job: marcar cuotas vencidas")
    try:
        # Importación diferida para evitar circular imports en arranque
        from ph_saas.database import SessionLocal
        from ph_saas.services.cuota_service import marcar_cuotas_vencidas

        db = SessionLocal()
        try:
            resultado = marcar_cuotas_vencidas(db)
            logger.info(f"[scheduler] Cuotas marcadas como Vencida: {resultado}")
        finally:
            db.close()
    except ImportError:
        logger.warning("[scheduler] cuota_service no disponible aún (Fase 2)")
    except Exception as e:
        logger.error(f"[scheduler] Error en job marcar_cuotas_vencidas: {e}")


def start_scheduler():
    """Iniciar el scheduler. Llamar desde main.py en startup."""
    scheduler.add_job(
        _marcar_cuotas_vencidas,
        trigger=CronTrigger(hour=0, minute=0, second=0),  # Medianoche Bogotá
        id="marcar_cuotas_vencidas",
        replace_existing=True,
        misfire_grace_time=3600,  # Tolerancia de 1 hora si el servidor estaba caído
    )
    scheduler.start()
    logger.info("[scheduler] APScheduler iniciado — job diario a medianoche configurado")


def stop_scheduler():
    """Detener el scheduler. Llamar desde main.py en shutdown."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("[scheduler] APScheduler detenido")
