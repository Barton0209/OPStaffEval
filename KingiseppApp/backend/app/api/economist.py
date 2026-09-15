"""Экономист: ведение ЧТС, история изменений, контроль незаполненных ставок.

Доступ: строго роль economist (require_roles(UserRole.economist)).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_roles
from app.models import Employee, RateHistory, User, UserRole
from app.schemas import EconomistRateUpdateIn, RateHistoryOut
from app.services.events import emit_event
from app.services.imports import nf
from app.services.tariff import grid_bounds, is_rate_expired

router = APIRouter(prefix="/api/economist", tags=["economist"])


def _get_employee(db: Session, user: User, tab_no: str) -> Employee:
    """Поиск сотрудника по табельному номеру (строгая нормализация, только своя организация)."""
    norm = nf(tab_no)
    emp = (
        db.query(Employee)
        .filter(Employee.organization_id == user.organization_id, Employee.tab_no == norm)
        .first()
    )
    if not emp:
        raise HTTPException(status_code=404, detail=f"Сотрудник с табельным {tab_no} не найден")
    return emp


@router.post("/update-rate")
def update_rate(
    body: EconomistRateUpdateIn,
    user: User = Depends(require_roles(UserRole.economist)),
    db: Session = Depends(get_db),
):
    """Изменение ЧТС: обновляет hourly_rate + rate_last_raised и пишет запись в RateHistory."""
    emp = _get_employee(db, user, body.tab_no)
    new_rate = round(float(body.new_rate), 2)
    old_rate = emp.hourly_rate
    if new_rate == (old_rate or 0.0) and emp.rate_last_raised == body.changed_at:
        raise HTTPException(status_code=400, detail="Нет изменений для сохранения")

    emp.hourly_rate = new_rate
    emp.rate_last_raised = body.changed_at
    emp.rate_updated_at = body.changed_at
    db.add(RateHistory(
        employee_id=emp.id,
        old_rate=old_rate,
        new_rate=new_rate,
        changed_at=body.changed_at,
        changed_by_user_id=user.id,
        comment=body.comment,
    ))
    emit_event(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        entity_type="employee",
        entity_id=emp.id,
        action="rate_updated",
        payload={
            "tab_no": emp.tab_no,
            "old_rate": old_rate,
            "new_rate": new_rate,
            "changed_at": body.changed_at.isoformat(),
            "source": "economist",
        },
    )
    db.commit()
    t_min, t_max = grid_bounds(db, emp.position_1c, emp.citizenship)
    return {
        "id": emp.id,
        "tab_no": emp.tab_no,
        "fio": emp.fio,
        "position_1c": emp.position_1c,
        "category": emp.category,
        "citizenship": emp.citizenship,
        "hourly_rate": emp.hourly_rate,
        "rate_last_raised": emp.rate_last_raised,
        "is_rate_expired": is_rate_expired(emp.rate_last_raised),
        "tariff_min": t_min,
        "tariff_max": t_max,
    }


@router.get("/employees")
def list_employees(
    q: str | None = Query(default=None, max_length=128),
    missing_rate_only: bool = False,
    limit: int = Query(default=200, le=2000),
    user: User = Depends(require_roles(UserRole.economist)),
    db: Session = Depends(get_db),
):
    """Список сотрудников для формы экономиста (поиск по табельному/ФИО + ЧТС)."""
    query = db.query(Employee).filter(Employee.organization_id == user.organization_id)
    if q:
        like = f"%{nf(q)}%"
        query = query.filter((Employee.fio.ilike(like)) | (Employee.tab_no.ilike(like)))
    if missing_rate_only:
        query = query.filter(
            (Employee.hourly_rate.is_(None)) | (Employee.hourly_rate <= 0)
        )
    out: list[dict] = []
    for e in query.order_by(Employee.fio).limit(limit).all():
        t_min, t_max = grid_bounds(db, e.position_1c, e.citizenship)
        out.append(
            {
                "id": e.id,
                "tab_no": e.tab_no,
                "fio": e.fio,
                "position_1c": e.position_1c,
                "department_1c": e.department_1c,
                "category": e.category,
                "citizenship": e.citizenship,
                "hire_date": e.hire_date,
                "probation_end_date": e.probation_end_date,
                "is_candidate": e.is_candidate,
                "hourly_rate": e.hourly_rate,
                "rate_last_raised": e.rate_last_raised,
                "is_rate_expired": is_rate_expired(e.rate_last_raised),
                "tariff_min": t_min,
                "tariff_max": t_max,
            }
        )
    return out


@router.get("/missing-rates")
def missing_rates(
    user: User = Depends(require_roles(UserRole.economist)),
    db: Session = Depends(get_db),
):
    """Счётчик и список сотрудников с незаполненной ЧТС (для бейджа экономиста)."""
    rows = (
        db.query(Employee)
        .filter(
            Employee.organization_id == user.organization_id,
            (Employee.hourly_rate.is_(None)) | (Employee.hourly_rate <= 0),
        )
        .order_by(Employee.fio)
        .all()
    )
    return {
        "count": len(rows),
        "items": [
            {
                "id": e.id,
                "tab_no": e.tab_no,
                "fio": e.fio,
                "position_1c": e.position_1c,
                "category": e.category,
            }
            for e in rows
        ],
    }


@router.get("/rate-history", response_model=list[RateHistoryOut])
def rate_history(
    employee_id: int = Query(...),
    user: User = Depends(require_roles(UserRole.economist)),
    db: Session = Depends(get_db),
):
    """История изменения ЧТС конкретного сотрудника (только своя организация)."""
    emp = db.get(Employee, employee_id)
    if not emp or emp.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    return (
        db.query(RateHistory)
        .filter(RateHistory.employee_id == emp.id)
        .order_by(RateHistory.changed_at.desc(), RateHistory.id.desc())
        .limit(200)
        .all()
    )