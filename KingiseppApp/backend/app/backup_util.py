"""Безопасный бэкап SQLite в WAL-режиме через sqlite3 backup API.

В отличие от простого копирования .db, sqlite3.backup() корректно сливает
WAL-журнал, поэтому резервная копия не теряет свежие транзакции.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from app.config import APP_ROOT, get_settings

logger = logging.getLogger(__name__)

BACKUP_KEEP = 14


def backup_database() -> Path | None:
    """Создаёт согласованный бэкап БД в backup_dir. Возвращает путь или None."""
    settings = get_settings()
    db_url = settings.database_url
    if not db_url.startswith("sqlite:///"):
        return None
    src_path = Path(db_url.replace("sqlite:///", ""))
    if not src_path.exists():
        return None

    backup_dir = APP_ROOT / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_path = backup_dir / f"kingisepp_{stamp}.db"

    src = sqlite3.connect(str(src_path))
    dst = sqlite3.connect(str(dest_path))
    try:
        with dst:
            src.backup(dst)
        # Принудительный checkpoint: записывает WAL в основной файл бэкапа.
        # Без этого WAL-файл источника может содержать транзакции, отсутствующие в бэкапе.
        src.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        src.close()
        dst.close()

    # Храним последние BACKUP_KEEP копий.
    files = sorted(
        backup_dir.glob("kingisepp_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in files[BACKUP_KEEP:]:
        try:
            old.unlink()
        except OSError:
            pass
    return dest_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = backup_database()
    logger.info("Backup saved: %s" if result else "Backup skipped (not SQLite)", result)