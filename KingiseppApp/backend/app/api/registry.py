from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.db import get_db
from app.deps import require_roles
from app.models import (
    Assignment,
    Employee,
    ProductionCoeff,
    User,
    UserRole,
)
from app.schemas import KvyрIn, RegistryRow
from app.services.evaluations import assignment_registry_status
from app.services.events import emit_event
from app.services.imports import ensure_org_and_period

router = APIRouter(prefix="/api/registry", tags=["registry"])
settings = get_settings()


def _months_since(d: date | None) -> int | None:
    if not d:
        return None
    today = date.today()
    return (today.year - d.year) * 12 + (today.month - d.month)


@router.get("/rows", response_model=list[RegistryRow])
def registry_rows(
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op, UserRole.site_chief)),
    db: Session = Depends(get_db),
) -> list[RegistryRow]:
    _, period = ensure_org_and_period(db, settings.org_code, settings.org_name)
    assignments = (
        db.query(Assignment)
        .options(
            joinedload(Assignment.employee),
            joinedload(Assignment.primary_user),
            joinedload(Assignment.secondary_user),
        )
        .filter(Assignment.period_id == period.id, Assignment.evaluate.is_(True))
        .all()
    )
    rows: list[RegistryRow] = []
    for asg in assignments:
        emp: Employee = asg.employee
        primary_ev, secondary_ev, p_avg, s_avg, status = assignment_registry_status(db, asg)
        coeff_row = (
            db.query(ProductionCoeff)
            .filter(
                ProductionCoeff.period_id == period.id,
                ProductionCoeff.employee_id == emp.id,
            )
            .order_by(ProductionCoeff.id.desc())
            .first()
        )
        if not coeff_row and asg.site_code:
            coeff_row = (
                db.query(ProductionCoeff)
                .filter(
                    ProductionCoeff.period_id == period.id,
                    ProductionCoeff.site_code == asg.site_code,
                    ProductionCoeff.employee_id.is_(None),
                )
                .order_by(ProductionCoeff.id.desc())
                .first()
            )
        k = coeff_row.coeff if coeff_row else 1.0
        final = None
        if status == "закрыто" and p_avg is not None:
            if asg.dual_enabled and s_avg is not None:
                final = round(((p_avg + s_avg) / 2) * k, 2)
            else:
                final = round(p_avg * k, 2)
        months = _months_since(emp.rate_updated_at)
        rows.append(
            RegistryRow(
                tab_no=emp.tab_no,
                fio=emp.fio,
                position=asg.position_fact or emp.position_1c,
                site_name=asg.site_name,
                primary_fio=(
                    primary_ev.evaluator.fio
                    if primary_ev is not None
                    else (asg.primary_user.fio if asg.primary_user else None)
                ),
                primary_avg=p_avg,
                secondary_fio=asg.secondary_user.fio if asg.secondary_user else None,
                secondary_avg=s_avg,
                k_vyr=k,
                final_score=final,
                status=status,
                hourly_rate=emp.hourly_rate,
                rate_updated_at=emp.rate_updated_at,
                months_since_rate_update=months,
                tariff_stale=bool(months is not None and months >= 6),
                employee_id=emp.id,
                assignment_id=asg.id,
            )
        )
    return rows


@router.post("/kvyr")
def upsert_kvyr(
    body: KvyрIn,
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op, UserRole.site_chief)),
    db: Session = Depends(get_db),
):
    if not body.employee_id and not body.site_code:
        raise HTTPException(status_code=400, detail="Нужен employee_id или site_code")
    _, period = ensure_org_and_period(db, settings.org_code, settings.org_name)
    row = ProductionCoeff(
        organization_id=user.organization_id,
        period_id=period.id,
        employee_id=body.employee_id,
        site_code=body.site_code,
        coeff=body.coeff,
        site_chief_user_id=user.id if user.role == UserRole.site_chief else None,
        comment=body.comment,
    )
    db.add(row)
    db.flush()
    emit_event(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        entity_type="production_coeff",
        entity_id=row.id,
        action="upserted",
        payload=body.model_dump(),
    )
    db.commit()
    return {"ok": True, "id": row.id, "coeff": row.coeff}
