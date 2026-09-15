from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.backup_util import backup_database
from app.db import SessionLocal
from app.models import DomainEvent, EvaluationPeriod
from app.services.evaluations import escalation_count

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def backup_db_job() -> None:
    """Бэкап БД с корректным слиянием WAL-журнала (см. app.backup_util)."""
    try:
        backup_database()
        logger.info("Backup completed successfully")
    except Exception as e:
        logger.error("Backup failed: %s", e, exc_info=True)


def escalation_scan_job() -> None:
    db = SessionLocal()
    try:
        period = (
            db.query(EvaluationPeriod)
            .filter(EvaluationPeriod.is_open.is_(True))
            .order_by(EvaluationPeriod.id.desc())
            .first()
        )
        n = (
            escalation_count(
                db,
                organization_id=period.organization_id,
                period_id=period.id,
            )
            if period
            else 0
        )
        logger.info("escalations period=%s count=%d", period.code if period else "-", n)
        # Отправка уведомления при наличии просроченных оценок
        if n > 0 and period:
            logger.warning(
                "ESCALATION ALERT: %d оценщиков не вошли в систему за N дней (period=%s)",
                n,
                period.code,
            )
    except Exception as e:
        logger.error("Escalation scan failed: %s", e, exc_info=True)
    finally:
        db.close()


def cleanup_events_job() -> None:
    """Удаляет DomainEvent старше 90 дней для экономии места в БД."""
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        deleted = db.query(DomainEvent).filter(DomainEvent.created_at < cutoff).delete()
        db.commit()
        if deleted > 0:
            logger.info("Cleaned up %d old DomainEvent records (>90 days)", deleted)
    except Exception as e:
        logger.error("Event cleanup failed: %s", e, exc_info=True)
    finally:
        db.close()


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(escalation_scan_job, "cron", hour=9, minute=0, id="escalations", replace_existing=True)
    scheduler.add_job(backup_db_job, "cron", hour=2, minute=0, id="backup", replace_existing=True)
    scheduler.add_job(cleanup_events_job, "cron", hour=3, minute=30, id="cleanup_events", replace_existing=True)
    # run once at startup for visibility
    scheduler.add_job(escalation_scan_job, "date", id="escalations_boot", replace_existing=True)
    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
