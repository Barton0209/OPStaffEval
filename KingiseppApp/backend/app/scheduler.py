from __future__ import annotations

import shutil
from datetime import datetime, timedelta
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.config import APP_ROOT, get_settings
from app.db import SessionLocal
from app.models import Assignment, Evaluation, EvaluationPeriod, EvaluationStatus, User

scheduler = BackgroundScheduler()


def backup_db_job() -> None:
    settings = get_settings()
    backup_dir = APP_ROOT / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    db_url = settings.database_url
    if not db_url.startswith("sqlite:///"):
        return
    src = Path(db_url.replace("sqlite:///", ""))
    if not src.exists():
        return
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(src, backup_dir / f"kingisepp_{stamp}.db")
    # keep last 14 backups
    files = sorted(backup_dir.glob("kingisepp_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[14:]:
        try:
            old.unlink()
        except OSError:
            pass


def _escalation_count(db: Session, period_id: int) -> int:
    threshold = datetime.utcnow() - timedelta(days=3)
    primaries = (
        db.query(Assignment.primary_user_id)
        .filter(
            Assignment.period_id == period_id,
            Assignment.evaluate.is_(True),
            Assignment.primary_user_id.is_not(None),
        )
        .distinct()
        .all()
    )
    count = 0
    for (uid,) in primaries:
        user = db.get(User, uid)
        if not user:
            continue
        pending = (
            db.query(Assignment)
            .filter(
                Assignment.period_id == period_id,
                Assignment.primary_user_id == uid,
                Assignment.evaluate.is_(True),
            )
            .count()
        )
        submitted = (
            db.query(Evaluation)
            .filter(
                Evaluation.evaluator_id == uid,
                Evaluation.status == EvaluationStatus.submitted,
                Evaluation.assignment_id.is_not(None),
            )
            .count()
        )
        if pending > submitted and (user.last_login_at is None or user.last_login_at < threshold):
            count += 1
    return count


def escalation_scan_job() -> None:
    settings = get_settings()
    log = settings.logs_dir / "escalations.log"
    db = SessionLocal()
    try:
        period = (
            db.query(EvaluationPeriod)
            .filter(EvaluationPeriod.is_open.is_(True))
            .order_by(EvaluationPeriod.id.desc())
            .first()
        )
        n = _escalation_count(db, period.id) if period else 0
        with log.open("a", encoding="utf-8") as f:
            code = period.code if period else "-"
            f.write(f"{datetime.now().isoformat()} period={code} escalations={n}\n")
    finally:
        db.close()


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(escalation_scan_job, "cron", hour=9, minute=0, id="escalations", replace_existing=True)
    scheduler.add_job(backup_db_job, "cron", hour=2, minute=0, id="backup", replace_existing=True)
    # run once at startup for visibility
    scheduler.add_job(escalation_scan_job, "date", id="escalations_boot", replace_existing=True)
    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
