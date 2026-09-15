"""Уведомления: счётчик неоценённых анкет для текущего пользователя.

Доступно любой авторизованной роли (master/foreman/site_chief/admin*).
Логика: открытый период → закрепления, где пользователь назначен 1-м или 2-м
оценщиком (evaluate=True), и у него нет сданной (submitted) анкеты.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.db import get_db
from app.deps import get_current_user
from app.models import Assignment, Evaluation, EvaluationStatus, User
from app.services.imports import ensure_org_and_period

router = APIRouter(prefix="/api/notifications", tags=["notifications"])
settings = get_settings()


@router.get("")
def notifications(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Список закреплений, где у пользователя не сдана анкета (бейдж-счётчик)."""
    _, period = ensure_org_and_period(db, settings.org_code, settings.org_name)

    assignments = (
        db.query(Assignment)
        .options(joinedload(Assignment.employee))
        .filter(
            Assignment.organization_id == user.organization_id,
            Assignment.period_id == period.id,
            Assignment.evaluate.is_(True),
            or_(
                Assignment.primary_user_id == user.id,
                Assignment.secondary_user_id == user.id,
            ),
        )
        .all()
    )
    if not assignments:
        return {"count": 0, "items": []}

    # Пакетно собираем свои оценки по всем закреплениям (без N+1).
    mine = (
        db.query(Evaluation)
        .filter(
            Evaluation.organization_id == user.organization_id,
            Evaluation.assignment_id.in_([a.id for a in assignments]),
            Evaluation.evaluator_id == user.id,
        )
        .all()
    )
    submitted_ids = {
        ev.assignment_id for ev in mine if ev.status == EvaluationStatus.submitted
    }

    items: list[dict] = []
    for asg in assignments:
        if asg.id in submitted_ids:
            continue
        emp = asg.employee
        is_secondary = asg.secondary_user_id == user.id and asg.primary_user_id != user.id
        items.append(
            {
                "assignment_id": asg.id,
                "employee_id": emp.id if emp else asg.employee_id,
                "fio": emp.fio if emp else "—",
                "tab_no": emp.tab_no if emp else "—",
                "site_name": asg.site_name,
                "my_role": "secondary" if is_secondary else "primary",
            }
        )

    return {"count": len(items), "items": items}