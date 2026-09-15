"""API для сводов, аналитики и выгрузок (Руководство ОП, ЦОК)."""

import io
import tempfile
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from openpyxl import Workbook
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.db import get_db
from app.deps import require_roles
from app.models import (
    Assignment,
    Employee,
    Evaluation,
    EvaluationPeriod,
    EvaluationStatus,
    Organization,
    ProductionCoeff,
    User,
    UserRole,
)
from app.services.imports import ensure_org_by_id, nf

router = APIRouter(prefix="/api/summary", tags=["summary"])
settings = get_settings()

# Настраиваемые диапазоны оценок (минимум включительно, максимум исключительно)
RANGES = [
    (1.0, 2.0, "1 – 2"),
    (2.0, 3.0, "2 – 3"),
    (3.0, 4.0, "3 – 4"),
    (4.0, 5.001, "4 – 5"),
]


def _final_score(p_avg: float | None, s_avg: float | None,
                  dual: bool, k: float | None, status: str) -> float | None:
    """Пересчёт итоговой оценки из реестра."""
    if status == "awaiting_primary":
        return None
    if p_avg is None:
        return None
    if dual and s_avg is not None:
        combined = round((p_avg + s_avg) / 2, 2)
    else:
        combined = p_avg
    if k is not None and k != 1.0:
        combined = round(combined * k, 2)
    return combined


def _kvyr_for(db: Session, period_id: int, emp_id: int, site_code: str | None) -> float | None:
    coeff = (
        db.query(ProductionCoeff)
        .filter(
            ProductionCoeff.period_id == period_id,
            ProductionCoeff.employee_id == emp_id,
        )
        .order_by(ProductionCoeff.id.desc())
        .first()
    )
    if not coeff and site_code:
        coeff = (
            db.query(ProductionCoeff)
            .filter(
                ProductionCoeff.period_id == period_id,
                ProductionCoeff.site_code == site_code,
            )
            .order_by(ProductionCoeff.id.desc())
            .first()
        )
    return float(coeff.coeff) if coeff else None


def _avg(ev) -> float | None:
    scores = [ev.score_quality, ev.score_discipline, ev.score_safety,
              ev.score_skills, ev.score_versatility]
    valid = [s for s in scores if s is not None]
    return round(sum(valid) / len(valid), 2) if valid else None


# ==================== Участки/отделы ====================


@router.get("/departments")
def list_departments(
    user: User = Depends(require_roles(UserRole.management_op, UserRole.admin, UserRole.cok_okit)),
    db: Session = Depends(get_db),
):
    """Список уникальных участков из назначений."""
    org, period = ensure_org_by_id(db, user.organization_id)

    # Cok_okit видит все площадки, management_op — только свою (если задана)
    base_filter = [
        Assignment.period_id == period.id,
        Assignment.evaluate.is_(True),
        Assignment.organization_id == org.id,
    ]

    assignments = (
        db.query(Assignment)
        .options(joinedload(Assignment.employee))
        .filter(*base_filter)
        .all()
    )

    # Фильтруем по участку для management_op
    if user.role == UserRole.management_op and user.site_name:
        assignments = [a for a in assignments if nf(user.site_name) in nf(a.site_name or "")]

    # Уникальные участки
    sites: dict[str, str] = {}
    for a in assignments:
        if a.site_name:
            sites[a.site_name] = a.site_name

    return sorted(sites.values())


# ==================== Диапазоны ====================


@router.get("/departments/{department}")
def department_ranges(
    department: str,
    user: User = Depends(require_roles(UserRole.management_op, UserRole.admin, UserRole.cok_okit)),
    db: Session = Depends(get_db),
):
    """Число сотрудников в каждом диапазоне для участка."""
    org, period = ensure_org_by_id(db, user.organization_id)

    assignments = (
        db.query(Assignment)
        .options(joinedload(Assignment.employee))
        .filter(
            Assignment.period_id == period.id,
            Assignment.evaluate.is_(True),
            Assignment.organization_id == org.id,
            Assignment.site_name == department,
        )
        .all()
    )

    if user.role == UserRole.management_op and user.site_name:
        assignments = [a for a in assignments if nf(user.site_name) in nf(a.site_name or "")]

    # Считаем итоговые оценки
    counts = {label: 0 for _, _, label in RANGES}
    for a in assignments:
        emp = a.employee
        primary_ev = (
            db.query(Evaluation)
            .filter(
                Evaluation.assignment_id == a.id,
                Evaluation.evaluator_id == a.primary_user_id,
                Evaluation.status == EvaluationStatus.submitted,
            )
            .first()
        )
        p_avg = _avg(primary_ev) if primary_ev else None

        s_avg = None
        if a.dual_enabled and a.secondary_user_id:
            secondary_ev = (
                db.query(Evaluation)
                .filter(
                    Evaluation.assignment_id == a.id,
                    Evaluation.evaluator_id == a.secondary_user_id,
                    Evaluation.status == EvaluationStatus.submitted,
                )
                .first()
            )
            s_avg = _avg(secondary_ev) if secondary_ev else None

        k = _kvyr_for(db, period.id, emp.id, a.site_code)
        final = _final_score(p_avg, s_avg, a.dual_enabled, k, "done")

        if final is not None:
            for lo, hi, label in RANGES:
                if lo <= final < hi:
                    counts[label] += 1
                    break

    return {"department": department, "ranges": counts}


@router.get("/departments/{department}/range/{range_label}")
def range_employees(
    department: str,
    range_label: str,
    user: User = Depends(require_roles(UserRole.management_op, UserRole.admin, UserRole.cok_okit)),
    db: Session = Depends(get_db),
):
    """Список сотрудников в диапазоне."""
    org, period = ensure_org_by_id(db, user.organization_id)

    # Находим границы диапазона
    bounds = None
    for lo, hi, label in RANGES:
        if label == range_label:
            bounds = (lo, hi)
            break
    if not bounds:
        raise HTTPException(status_code=404, detail="Диапазон не найден")

    lo, hi = bounds

    assignments = (
        db.query(Assignment)
        .options(joinedload(Assignment.employee))
        .filter(
            Assignment.period_id == period.id,
            Assignment.evaluate.is_(True),
            Assignment.organization_id == org.id,
            Assignment.site_name == department,
        )
        .all()
    )

    if user.role == UserRole.management_op and user.site_name:
        assignments = [a for a in assignments if nf(user.site_name) in nf(a.site_name or "")]

    result = []
    for a in assignments:
        emp = a.employee
        primary_ev = (
            db.query(Evaluation)
            .filter(
                Evaluation.assignment_id == a.id,
                Evaluation.evaluator_id == a.primary_user_id,
                Evaluation.status == EvaluationStatus.submitted,
            )
            .first()
        )
        p_avg = _avg(primary_ev) if primary_ev else None

        s_avg = None
        if a.dual_enabled and a.secondary_user_id:
            secondary_ev = (
                db.query(Evaluation)
                .filter(
                    Evaluation.assignment_id == a.id,
                    Evaluation.evaluator_id == a.secondary_user_id,
                    Evaluation.status == EvaluationStatus.submitted,
                )
                .first()
            )
            s_avg = _avg(secondary_ev) if secondary_ev else None

        k = _kvyr_for(db, period.id, emp.id, a.site_code)
        final = _final_score(p_avg, s_avg, a.dual_enabled, k, "done")

        if final is not None and lo <= final < hi:
            result.append({
                "employee_id": emp.id,
                "tab_no": emp.tab_no,
                "fio": emp.fio,
                "position": a.position_fact or emp.position_1c,
                "site_name": a.site_name,
                "final_score": final,
                "hourly_rate": emp.hourly_rate,
                "category": emp.category,
                "citizenship": emp.citizenship,
            })

    return {"department": department, "range": range_label, "count": len(result), "employees": result}


@router.get("/departments/{department}/range/{range_label}/export.xlsx")
def export_range_excel(
    department: str,
    range_label: str,
    user: User = Depends(require_roles(UserRole.management_op, UserRole.admin, UserRole.cok_okit)),
    db: Session = Depends(get_db),
):
    """Выгрузка сотрудников диапазона в Excel."""
    bounds = None
    for lo, hi, label in RANGES:
        if label == range_label:
            bounds = (lo, hi)
            break
    if not bounds:
        raise HTTPException(status_code=404, detail="Диапазон не найден")

    org, period = ensure_org_by_id(db, user.organization_id)

    assignments = (
        db.query(Assignment)
        .options(joinedload(Assignment.employee))
        .filter(
            Assignment.period_id == period.id,
            Assignment.evaluate.is_(True),
            Assignment.organization_id == org.id,
            Assignment.site_name == department,
        )
        .all()
    )

    if user.role == UserRole.management_op and user.site_name:
        assignments = [a for a in assignments if nf(user.site_name) in nf(a.site_name or "")]

    wb = Workbook()
    ws = wb.active
    ws.title = f"Диапазон {range_label}"
    ws.append(["Табельный", "ФИО", "Должность", "Участок", "Итоговая оценка",
                "Разряд", "ЧТС", "Гражданство"])

    for a in assignments:
        emp = a.employee
        primary_ev = (
            db.query(Evaluation)
            .filter(
                Evaluation.assignment_id == a.id,
                Evaluation.evaluator_id == a.primary_user_id,
                Evaluation.status == EvaluationStatus.submitted,
            )
            .first()
        )
        p_avg = _avg(primary_ev) if primary_ev else None

        s_avg = None
        if a.dual_enabled and a.secondary_user_id:
            secondary_ev = (
                db.query(Evaluation)
                .filter(
                    Evaluation.assignment_id == a.id,
                    Evaluation.evaluator_id == a.secondary_user_id,
                    Evaluation.status == EvaluationStatus.submitted,
                )
                .first()
            )
            s_avg = _avg(secondary_ev) if secondary_ev else None

        k = _kvyr_for(db, period.id, emp.id, a.site_code)
        final = _final_score(p_avg, s_avg, a.dual_enabled, k, "done")

        lo, hi = bounds
        if final is not None and lo <= final < hi:
            ws.append([
                emp.tab_no, emp.fio,
                a.position_fact or emp.position_1c or "",
                a.site_name or "",
                final,
                emp.category or "",
                emp.hourly_rate or "",
                emp.citizenship or "",
            ])

    fd, path = tempfile.mkstemp(suffix=".xlsx", prefix="summary_")
    import os
    os.close(fd)
    wb.save(path)

    return FileResponse(
        path,
        filename=f"{department}_{range_label}_{date.today()}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
