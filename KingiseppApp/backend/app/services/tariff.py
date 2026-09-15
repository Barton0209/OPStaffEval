"""Утилиты ЧТС и тарифной сетки: срок давности, гражданство, границы вилки."""
from __future__ import annotations

import re
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.models import TariffGrid

# Порог «ЧТС давно не поднимали» — 6 месяцев (180 дней).
RATE_EXPIRY_DAYS = 180

# Приводим название гражданства к единому виду для поиска в тарифной сетке.
_CITIZENSHIP_GROUP_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"ИНДИ"), "Индия"),
    (re.compile(r"СЕРБИ"), "Сербия, БиГ"),
    (re.compile(r"\bБИГ\b"), "Сербия, БиГ"),
    (re.compile(r"РОСС"), "РФ, Белоруссия"),
    # БЕЛАРУСЬ и БЕЛОРУССИЯ (обе формы в файлах).
    (re.compile(r"БЕЛ(?:А|О)РУС"), "РФ, Белоруссия"),
    (re.compile(r"КАЗАХ"), "Казахстан, Киргизия"),
    (re.compile(r"КИРГИЗ"), "Казахстан, Киргизия"),
    (re.compile(r"УЗБЕК"), "Туркмения, Узбекистан, Таджикистан"),
    (re.compile(r"ТАДЖИК"), "Туркмения, Узбекистан, Таджикистан"),
    (re.compile(r"ТУРКМЕН"), "Туркмения, Узбекистан, Таджикистан"),
]

# Канонические названия групп из Сводная_тарифная_сетка.xlsx.
KNOWN_GROUPS = (
    "Индия",
    "Сербия, БиГ",
    "РФ, Белоруссия",
    "Казахстан, Киргизия",
    "Туркмения, Узбекистан, Таджикистан",
)


def is_rate_expired(rate_last_raised: date | None, *, today: date | None = None) -> bool:
    """True, если с даты последнего поднятия ЧТС прошло >= 180 дней.

    Используется aware UTC-время (datetime.now(timezone.utc)) как источник «сегодня».
    """
    if not rate_last_raised:
        return False
    now_utc = datetime.now(timezone.utc)
    ref = today or now_utc.date()
    return (ref - rate_last_raised).days >= RATE_EXPIRY_DAYS


def citizenship_group(raw: str | None) -> str | None:
    """Сопоставляет гражданство сотрудника с группой тарифной сетки.

    Примеры: 'УЗБЕКИСТАН' → 'Туркмения, Узбекистан, Таджикистан',
    'РОССИЯ'/'БЕЛАРУСЬ' → 'РФ, Белоруссия'.
    """
    if not raw:
        return None
    norm = re.sub(r"[^\w\u0400-\u04FF]", "", str(raw).upper(), flags=re.UNICODE)
    if not norm:
        return None
    for pattern, group in _CITIZENSHIP_GROUP_RULES:
        if pattern.search(norm):
            return group
    # Точное совпадение с уже каноническим названием (например, из самой сетки).
    for group in KNOWN_GROUPS:
        if re.sub(r"[^\w\u0400-\u04FF]", "", group.upper()) == norm:
            return group
    return None


def grid_bounds(
    db: Session,
    position: str | None,
    citizenship: str | None,
) -> tuple[float | None, float | None]:
    """(min_rate, max_rate) из тарифной сетки для должности и гражданства."""
    if not position:
        return None, None
    pos_norm = _norm_position(position)
    group = citizenship_group(citizenship)

    rows = (
        db.query(TariffGrid)
        .filter(TariffGrid.position.in_([position, pos_norm]))
        .all()
    )
    best = None
    for row in rows:
        if group and row.citizenship == group:
            best = row
            break
    if best is None and rows:
        # Не знаем гражданство или нет точной группы — берём первую подходящую должность.
        best = rows[0]
    if best is None:
        return None, None
    return (best.min_rate or None), (best.max_rate or None)


def _norm_position(position: str) -> str:
    return re.sub(r"\s+", " ", str(position or "").strip())


# ---------- Пакетный поиск (без N+1 для списков) ----------

GridIndex = dict[str, list[tuple[str, float, float]]]  # position -> [(citizenship, min, max)]


def load_grid_index(db: Session) -> GridIndex:
    """Загружает всю тарифную сетку одним запросом: должность → список (гражданство, мин, макс)."""
    index: GridIndex = {}
    for row in db.query(TariffGrid).all():
        index.setdefault(row.position, []).append((row.citizenship, row.min_rate, row.max_rate))
    return index


def bounds_from_index(
    index: GridIndex,
    position: str | None,
    citizenship: str | None,
) -> tuple[float | None, float | None]:
    """(min_rate, max_rate) из предзагруженного индекса сетки."""
    pos = str(position or "").strip()
    if not pos:
        return None, None
    rows = index.get(pos) or index.get(_norm_position(pos))
    if not rows:
        return None, None
    group = citizenship_group(citizenship)
    for cit, mn, mx in rows:
        if group and cit == group:
            return (mn or None), (mx or None)
    mn, mx = rows[0][1], rows[0][2]
    return (mn or None), (mx or None)