from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
import shutil

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import require_roles
from app.models import (
    Assignment,
    Delegation,
    Employee,
    Evaluation,
    EvaluationStatus,
    ListTicket,
    UrgentEvaluator,
    UrgentRequest,
    User,
    UserRole,
)
from app.schemas import (
    DashboardOut,
    DelegationIn,
    EmployeeCreateIn,
    FormalizeCandidateIn,
    ImportResult,
    TicketOut,
)
from app.services.evaluations import count_closed_assignments, repair_completed_urgents
from app.services.events import emit_event
from app.services.imports import (
    ensure_org_and_period,
    import_base,
    import_carnet,
    import_users,
    resolve_assignment_registry_path,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])
settings = get_settings()


class UrgentCreateIn(BaseModel):
    employee_id: int
    evaluator_user_ids: list[int] = Field(min_length=1)
    comment: str | None = None


class AssignPrimaryIn(BaseModel):
    primary_user_id: int | None = None
    evaluate: bool | None = None
    dual_enabled: bool | None = None
    secondary_user_id: int | None = None


class TicketPatchIn(BaseModel):
    status: str | None = None
    admin_note: str | None = None


def _escalation_count(db: Session, org_id: int, period_id: int) -> int:
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


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
) -> DashboardOut:
    org, period = ensure_org_and_period(db, settings.org_code, settings.org_name)
    # Починить уже отвеченные, но незакрытые срочные (старые данные)
    repair_completed_urgents(db)
    total = db.query(Assignment).filter(Assignment.period_id == period.id).count()
    evaluate_yes = (
        db.query(Assignment)
        .filter(Assignment.period_id == period.id, Assignment.evaluate.is_(True))
        .count()
    )
    with_primary = (
        db.query(Assignment)
        .filter(Assignment.period_id == period.id, Assignment.primary_user_id.is_not(None))
        .count()
    )
    awaiting = (
        db.query(Assignment)
        .filter(Assignment.period_id == period.id, Assignment.primary_user_id.is_(None))
        .count()
    )
    candidates = (
        db.query(Employee)
        .filter(Employee.organization_id == org.id, Employee.is_candidate.is_(True))
        .count()
    )
    submitted = count_closed_assignments(db, period.id)
    dual = (
        db.query(Assignment)
        .filter(Assignment.period_id == period.id, Assignment.dual_enabled.is_(True))
        .count()
    )
    open_urgent = (
        db.query(UrgentRequest)
        .filter(UrgentRequest.organization_id == org.id, UrgentRequest.status == "open")
        .count()
    )
    open_tickets = (
        db.query(ListTicket)
        .filter(
            ListTicket.organization_id == org.id,
            ListTicket.status.in_(["new", "in_progress"]),
        )
        .count()
    )
    return DashboardOut(
        organization=org.name,
        period_code=period.code,
        total_assignments=total,
        evaluate_yes=evaluate_yes,
        with_primary=with_primary,
        awaiting_primary=awaiting,
        candidates=candidates,
        submitted_evaluations=submitted,
        dual_enabled=dual,
        open_urgent=open_urgent,
        open_tickets=open_tickets,
        escalations=_escalation_count(db, org.id, period.id),
    )


@router.post("/import/all", response_model=list[ImportResult])
def import_all_excel(
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
) -> list[ImportResult]:
    files_dir = settings.files_path
    org, period = ensure_org_and_period(db, settings.org_code, settings.org_name)
    base = files_dir / "01_База_1С.xlsx"
    users = files_dir / "02_Пользователи.xlsx"
    registry = resolve_assignment_registry_path(files_dir)
    if not base.exists() or not users.exists() or not registry:
        raise HTTPException(
            status_code=400,
            detail=f"Нужны файлы 01_База_1С, 02_Пользователи и 03_Реестр_закрепления в {files_dir}",
        )
    return [
        import_base(db, base, org, user.id),
        import_users(db, users, org, user.id),
        import_carnet(db, registry, org, period, user.id),
    ]


@router.post("/import/upload", response_model=list[ImportResult])
async def import_upload(
    base_file: UploadFile | None = File(None, description="01_База_1С.xlsx"),
    users_file: UploadFile | None = File(None, description="02_Пользователи.xlsx"),
    carnet_file: UploadFile | None = File(None, description="03_Реестр_закрепления.xlsx"),
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
) -> list[ImportResult]:
    """Загрузка Excel прямо из браузера."""
    if not base_file and not users_file and not carnet_file:
        raise HTTPException(status_code=400, detail="Выберите хотя бы один Excel-файл")
    org, period = ensure_org_and_period(db, settings.org_code, settings.org_name)
    files_dir = settings.files_path
    files_dir.mkdir(parents=True, exist_ok=True)
    results: list[ImportResult] = []

    async def _save(upload: UploadFile, target_name: str) -> Path:
        dest = files_dir / target_name
        with dest.open("wb") as out:
            shutil.copyfileobj(upload.file, out)
        return dest

    if base_file and base_file.filename:
        path = await _save(base_file, "01_База_1С.xlsx")
        results.append(import_base(db, path, org, user.id))
    if users_file and users_file.filename:
        path = await _save(users_file, "02_Пользователи.xlsx")
        results.append(import_users(db, path, org, user.id))
    if carnet_file and carnet_file.filename:
        path = await _save(carnet_file, "03_Реестр_закрепления.xlsx")
        results.append(import_carnet(db, path, org, period, user.id))
    return results


@router.get("/assignments")
def list_assignments(
    evaluate: bool | None = None,
    awaiting_primary: bool | None = None,
    q: str | None = None,
    limit: int = 2000,
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
):
    _, period = ensure_org_and_period(db, settings.org_code, settings.org_name)
    query = (
        db.query(Assignment, Employee, User)
        .join(Employee, Employee.id == Assignment.employee_id)
        .outerjoin(User, User.id == Assignment.primary_user_id)
        .filter(Assignment.period_id == period.id)
    )
    if evaluate is not None:
        query = query.filter(Assignment.evaluate.is_(evaluate))
    if awaiting_primary:
        query = query.filter(Assignment.primary_user_id.is_(None))
    if q:
        like = f"%{q}%"
        query = query.filter((Employee.fio.ilike(like)) | (Employee.tab_no.ilike(like)))
    rows = query.order_by(Employee.fio).limit(limit).all()
    return [
        {
            "assignment_id": a.id,
            "employee_id": e.id,
            "tab_no": e.tab_no,
            "fio": e.fio,
            "is_candidate": e.is_candidate,
            "site_code": a.site_code,
            "site_name": a.site_name,
            "evaluate": a.evaluate,
            "primary_fio": p.fio if p else None,
            "primary_tab": p.tab_no if p else None,
            "primary_user_id": a.primary_user_id,
            "dual_enabled": a.dual_enabled,
            "secondary_user_id": a.secondary_user_id,
            "worker_status": a.worker_status,
            "version": a.version,
        }
        for a, e, p in rows
    ]


@router.patch("/assignments/{assignment_id}")
def patch_assignment(
    assignment_id: int,
    body: AssignPrimaryIn,
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
):
    asg = db.get(Assignment, assignment_id)
    if not asg:
        raise HTTPException(status_code=404, detail="Не найдено")
    data = body.model_dump(exclude_unset=True)
    if "primary_user_id" in data:
        asg.primary_user_id = data["primary_user_id"]
    if "evaluate" in data:
        asg.evaluate = bool(data["evaluate"])
    if "dual_enabled" in data:
        asg.dual_enabled = bool(data["dual_enabled"])
    if "secondary_user_id" in data:
        asg.secondary_user_id = data["secondary_user_id"]
    if asg.dual_enabled and not asg.secondary_user_id:
        raise HTTPException(status_code=400, detail="dual требует secondary")
    if asg.evaluate and not asg.primary_user_id:
        raise HTTPException(status_code=400, detail="evaluate=yes требует primary")
    if not asg.dual_enabled:
        asg.secondary_user_id = None
    asg.version = (asg.version or 1) + 1
    emit_event(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        entity_type="assignment",
        entity_id=asg.id,
        action="updated",
        payload=data,
    )
    db.commit()
    return {"ok": True, "version": asg.version}


@router.post("/urgent")
def create_urgent(
    body: UrgentCreateIn,
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
):
    emp = db.get(Employee, body.employee_id)
    if not emp or emp.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Сотрудник не найден в Базе")
    if emp.is_candidate:
        raise HTTPException(status_code=400, detail="Сначала оформите кандидата в Базе (tab_no)")
    ur = UrgentRequest(
        organization_id=user.organization_id,
        employee_id=emp.id,
        created_by_user_id=user.id,
        comment=body.comment,
        status="open",
    )
    db.add(ur)
    db.flush()
    for uid in body.evaluator_user_ids:
        u = db.get(User, uid)
        if not u or u.role not in (UserRole.master, UserRole.foreman):
            raise HTTPException(status_code=400, detail=f"Недопустимый оценивающий id={uid}")
        db.add(UrgentEvaluator(urgent_request_id=ur.id, user_id=uid))
    emit_event(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        entity_type="urgent_request",
        entity_id=ur.id,
        action="created",
        payload={"employee_id": emp.id, "evaluators": body.evaluator_user_ids},
    )
    db.commit()
    return {"urgent_request_id": ur.id, "status": "open"}


@router.post("/urgent/{urgent_id}/close")
def close_urgent(
    urgent_id: int,
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
):
    ur = db.get(UrgentRequest, urgent_id)
    if not ur:
        raise HTTPException(status_code=404, detail="Не найдено")
    ur.status = "closed"
    ur.closed_at = datetime.utcnow()
    emit_event(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        entity_type="urgent_request",
        entity_id=ur.id,
        action="closed",
        payload={},
    )
    db.commit()
    return {"ok": True}


@router.get("/urgent")
def list_urgent(
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(UrgentRequest, Employee)
        .join(Employee, Employee.id == UrgentRequest.employee_id)
        .filter(UrgentRequest.organization_id == user.organization_id)
        .order_by(UrgentRequest.id.desc())
        .limit(100)
        .all()
    )
    out = []
    for ur, emp in rows:
        evals = db.query(UrgentEvaluator).filter(UrgentEvaluator.urgent_request_id == ur.id).all()
        out.append(
            {
                "id": ur.id,
                "status": ur.status,
                "comment": ur.comment,
                "employee_id": emp.id,
                "tab_no": emp.tab_no,
                "fio": emp.fio,
                "evaluator_ids": [e.user_id for e in evals],
                "created_at": ur.created_at,
            }
        )
    return out


@router.post("/delegations")
def create_delegation(
    body: DelegationIn,
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
):
    _, period = ensure_org_and_period(db, settings.org_code, settings.org_name)
    orig = db.get(User, body.original_user_id)
    sub = db.get(User, body.substitute_user_id)
    if not orig or not sub:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if sub.role not in (UserRole.master, UserRole.foreman):
        raise HTTPException(status_code=400, detail="Заместитель должен быть мастер/ПР")
    if body.ends_on < body.starts_on:
        raise HTTPException(status_code=400, detail="Неверный период")
    d = Delegation(
        organization_id=user.organization_id,
        period_id=period.id,
        original_user_id=orig.id,
        substitute_user_id=sub.id,
        starts_on=body.starts_on,
        ends_on=body.ends_on,
        reason=body.reason,
        created_by_user_id=user.id,
        is_active=True,
    )
    db.add(d)
    db.flush()
    emit_event(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        entity_type="delegation",
        entity_id=d.id,
        action="created",
        payload=body.model_dump(mode="json"),
    )
    db.commit()
    return {"delegation_id": d.id}


@router.get("/delegations")
def list_delegations(
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Delegation)
        .filter(Delegation.organization_id == user.organization_id)
        .order_by(Delegation.id.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": d.id,
            "original_user_id": d.original_user_id,
            "substitute_user_id": d.substitute_user_id,
            "starts_on": d.starts_on,
            "ends_on": d.ends_on,
            "reason": d.reason,
            "is_active": d.is_active,
        }
        for d in rows
    ]


@router.post("/delegations/{delegation_id}/deactivate")
def deactivate_delegation(
    delegation_id: int,
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
):
    d = db.get(Delegation, delegation_id)
    if not d:
        raise HTTPException(status_code=404, detail="Не найдено")
    d.is_active = False
    db.commit()
    return {"ok": True}


@router.get("/users")
def list_users(
    role: UserRole | None = None,
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
):
    q = db.query(User).filter(User.organization_id == user.organization_id, User.status == "Активен")
    if role:
        q = q.filter(User.role == role)
    return [
        {
            "id": u.id,
            "tab_no": u.tab_no,
            "fio": u.fio,
            "role": u.role.value,
            "site_code": u.site_code,
            "last_login_at": u.last_login_at,
        }
        for u in q.order_by(User.fio).all()
    ]


@router.get("/employees")
def list_employees(
    q: str | None = None,
    candidates_only: bool = False,
    limit: int = 200,
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
):
    query = db.query(Employee).filter(Employee.organization_id == user.organization_id)
    if candidates_only:
        query = query.filter(Employee.is_candidate.is_(True))
    if q:
        like = f"%{q}%"
        query = query.filter((Employee.fio.ilike(like)) | (Employee.tab_no.ilike(like)))
    return [
        {
            "id": e.id,
            "tab_no": e.tab_no,
            "fio": e.fio,
            "position_1c": e.position_1c,
            "is_candidate": e.is_candidate,
            "hire_date": e.hire_date,
            "hourly_rate": e.hourly_rate,
            "rate_updated_at": e.rate_updated_at,
        }
        for e in query.order_by(Employee.fio).limit(limit).all()
    ]


@router.post("/employees")
def create_employee(
    body: EmployeeCreateIn,
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
):
    exists = (
        db.query(Employee)
        .filter(Employee.organization_id == user.organization_id, Employee.tab_no == body.tab_no)
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="tab_no уже есть в Базе")
    emp = Employee(
        organization_id=user.organization_id,
        tab_no=body.tab_no.strip(),
        fio=body.fio.strip(),
        position_1c=body.position_1c,
        department_1c=body.department_1c,
        hire_date=body.hire_date,
        is_candidate=body.is_candidate,
    )
    db.add(emp)
    db.flush()
    emit_event(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        entity_type="employee",
        entity_id=emp.id,
        action="created",
        payload=body.model_dump(mode="json"),
    )
    db.commit()
    return {"employee_id": emp.id}


@router.post("/employees/formalize-candidate")
def formalize_candidate(
    body: FormalizeCandidateIn,
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
):
    emp = db.get(Employee, body.employee_id)
    if not emp or not emp.is_candidate:
        raise HTTPException(status_code=404, detail="Кандидат не найден")
    clash = (
        db.query(Employee)
        .filter(
            Employee.organization_id == user.organization_id,
            Employee.tab_no == body.new_tab_no,
            Employee.id != emp.id,
        )
        .first()
    )
    if clash:
        raise HTTPException(status_code=400, detail="Такой tab_no уже занят")
    old = emp.tab_no
    emp.tab_no = body.new_tab_no.strip()
    emp.is_candidate = False
    if body.hire_date:
        emp.hire_date = body.hire_date
    if body.position_1c:
        emp.position_1c = body.position_1c
    emit_event(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        entity_type="employee",
        entity_id=emp.id,
        action="formalized",
        payload={"from": old, "to": emp.tab_no},
    )
    db.commit()
    return {"ok": True, "tab_no": emp.tab_no}


@router.get("/tickets", response_model=list[TicketOut])
def list_tickets(
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(ListTicket, User)
        .outerjoin(User, User.id == ListTicket.created_by_user_id)
        .filter(ListTicket.organization_id == user.organization_id)
        .order_by(ListTicket.id.desc())
        .limit(200)
        .all()
    )
    out: list[TicketOut] = []
    for t, author in rows:
        out.append(
            TicketOut(
                id=t.id,
                message=t.message,
                status=t.status,
                assignment_id=t.assignment_id,
                employee_id=t.employee_id,
                created_by_user_id=t.created_by_user_id,
                created_by_fio=author.fio if author else None,
                created_by_tab_no=author.tab_no if author else None,
                admin_note=t.admin_note,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
        )
    return out


@router.patch("/tickets/{ticket_id}", response_model=TicketOut)
def patch_ticket(
    ticket_id: int,
    body: TicketPatchIn,
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
):
    t = db.get(ListTicket, ticket_id)
    if not t:
        raise HTTPException(status_code=404, detail="Не найдено")
    if body.status is not None:
        if body.status not in {"new", "in_progress", "done"}:
            raise HTTPException(status_code=400, detail="Неверный статус")
        t.status = body.status
    if body.admin_note is not None:
        t.admin_note = body.admin_note.strip() or None
        if t.admin_note and t.status == "new":
            t.status = "in_progress"
    emit_event(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        entity_type="list_ticket",
        entity_id=t.id,
        action="updated",
        payload=body.model_dump(exclude_unset=True),
    )
    db.commit()
    db.refresh(t)
    author = db.get(User, t.created_by_user_id)
    return TicketOut(
        id=t.id,
        message=t.message,
        status=t.status,
        assignment_id=t.assignment_id,
        employee_id=t.employee_id,
        created_by_user_id=t.created_by_user_id,
        created_by_fio=author.fio if author else None,
        created_by_tab_no=author.tab_no if author else None,
        admin_note=t.admin_note,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


@router.get("/events")
def list_events(
    entity_type: str | None = None,
    limit: int = 100,
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
):
    from app.models import DomainEvent

    q = db.query(DomainEvent).filter(DomainEvent.organization_id == user.organization_id)
    if entity_type:
        q = q.filter(DomainEvent.entity_type == entity_type)
    rows = q.order_by(DomainEvent.id.desc()).limit(limit).all()
    return [
        {
            "id": e.id,
            "created_at": e.created_at,
            "actor_user_id": e.actor_user_id,
            "entity_type": e.entity_type,
            "entity_id": e.entity_id,
            "action": e.action,
            "payload_json": e.payload_json,
        }
        for e in rows
    ]


@router.get("/escalations")
def list_escalations(
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
):
    _, period = ensure_org_and_period(db, settings.org_code, settings.org_name)
    threshold = datetime.utcnow() - timedelta(days=3)
    out = []
    primaries = (
        db.query(Assignment.primary_user_id)
        .filter(
            Assignment.period_id == period.id,
            Assignment.evaluate.is_(True),
            Assignment.primary_user_id.is_not(None),
        )
        .distinct()
        .all()
    )
    for (uid,) in primaries:
        u = db.get(User, uid)
        if not u:
            continue
        pending = (
            db.query(Assignment)
            .filter(
                Assignment.period_id == period.id,
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
        if pending > submitted and (u.last_login_at is None or u.last_login_at < threshold):
            out.append(
                {
                    "user_id": u.id,
                    "tab_no": u.tab_no,
                    "fio": u.fio,
                    "last_login_at": u.last_login_at,
                    "pending_assignments": pending,
                    "submitted": submitted,
                }
            )
    return out
