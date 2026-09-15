from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_MAX_BYTES = 5 * 1024 * 1024  # 5 МБ на файл
_BACKUP_COUNT = 5

_configured = False


def setup_logging(logs_dir: Path, level: int = logging.INFO) -> None:
    """Единая конфигурация логирования: файл с ротацией + консоль.

    Идемпотентна: повторные вызовы (reload/повторный lifespan) не плодят хендлеры.
    Логи uvicorn (access/error) наследуют корневой конфиг — всё пишется в app.log.
    """
    global _configured
    if _configured:
        return
    logs_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)
    fmt = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    file_handler = RotatingFileHandler(
        logs_dir / "app.log",
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(fmt)

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(fmt)

    root.addHandler(file_handler)
    root.addHandler(console)

    # uvicorn-логгеры прокидываем в корень, чтобы они попадали и в файл.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True

    _configured = True