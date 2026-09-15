from __future__ import annotations

from datetime import date, datetime, timezone
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
    DomainEvent,
    Employee,
    Evaluation,
    EvaluationStatus,
    ListTicket,
    TariffGrid,
    TicketStatus,
    UrgentEvaluator,
    UrgentRequest,
    UrgentStatus,
    User,
    UserRole,
    UserStatus,
)
from app.schemas import (
    DashboardOut,
    DelegationIn,
    EmployeeCreateIn,
    EmployeePatchIn,
    FormalizeCandidateIn,
    ImportResult,
    SecondAssignIn,
    TariffGridOut,
    TicketOut,
    UserCreateIn,
    UserPatchIn,
)
from app.security import hash_password
from app.services.evaluations import (
    count_closed_assignments,
    covering_evaluator_ids,
    escalation_count,
    escalation_report,
    repair_completed_urgents,
)
from app.services.events import emit_event
from app.services.imports import (
    ensure_org_and_period,
    ensure_org_by_id,
    import_base,
    import_carnet,
    import_daily_assignees,
    import_tariff_grid,
    import_ud_rates,
    import_users,
    nf,
    resolve_assignment_registry_path,
)
from app.services.tariff import grid_bounds, is_rate_expired

router = APIRouter(prefix="/api/admin", tags=["admin"])
settings = get_settings()


def get_org_object(db: Session, model, obj_id: int, user: User):
    """Достаёт объект и проверяет принадлежность организации авторизованного пользователя."""
    obj = db.get(model, obj_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Не найдено")
    if getattr(obj, "organization_id", None) != user.organization_id:
        # 403 вместо 404 — предотвращает enumeration объектов между организациями
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    return obj


class UrgentCreateIn(BaseModel):
    employee_id: int
    evaluator_user_ids: list[int] = Field(min_length=1)
    comment: str | None = None


class AssignPrimaryIn(BaseModel):
    primary_user_id: int | None = None
    evaluate: bool | None = None
    dual_enabled: bool | None = None
    secondary_user_id: int | None = None


class BulkAssignmentsIn(BaseModel):
    assignment_ids: list[int] = Field(min_length=1)
    primary_user_id: int | None = None
    evaluate: bool | None = None


class TicketPatchIn(BaseModel):
    status: str | None = None
    admin_note: str | None = None


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
) -> DashboardOut:
    org, period = ensure_org_by_id(db, user.organization_id)
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
        .filter(
            UrgentRequest.organization_id == org.id,
            UrgentRequest.status == UrgentStatus.open,
        )
        .count()
    )
    open_tickets = (
        db.query(ListTicket)
        .filter(
            ListTicket.organization_id == org.id,
            ListTicket.status.in_([TicketStatus.new, TicketStatus.in_progress]),
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
        escalations=escalation_count(db, organization_id=org.id, period_id=period.id),
    )


@router.post("/import/all", response_model=list[ImportResult])
def import_all_excel(
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
) -> list[ImportResult]:
    files_dir = settings.files_path
    org, period = ensure_org_by_id(db, user.organization_id)
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
    ud_file: UploadFile | None = File(None, description="УД_Список сотрудников (.xlsb)"),
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
) -> list[ImportResult]:
    """Загрузка Excel прямо из браузера."""
    if not base_file and not users_file and not carnet_file and not ud_file:
        raise HTTPException(status_code=400, detail="Выберите хотя бы один Excel-файл")
    org, period = ensure_org_by_id(db, user.organization_id)
    files_dir = settings.files_path
    files_dir.mkdir(parents=True, exist_ok=True)
    results: list[ImportResult] = []

    max_bytes = settings.max_upload_mb * 1024 * 1024
    XLSX_MAGIC = b"PK\x03\x04"

    async def _save(upload: UploadFile, target_name: str) -> Path:
        # Валидация: сигнатура xlsx/xlsb (zip-контейнер) и лимит размера.
        head = await upload.read(4)
        await upload.seek(0)
        if head != XLSX_MAGIC:
            raise HTTPException(
                status_code=400,
                detail=f"{target_name}: файл не является Excel (.xlsx/.xlsb)",
            )
        content = await upload.read(max_bytes + 1)
        await upload.seek(0)
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"{target_name}: размер превышает {settings.max_upload_mb} МБ",
            )
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
    if ud_file and ud_file.filename:
        path = await _save(ud_file, "УД_Список_сотрудников.xlsb")
        results.append(import_ud_rates(db, path, org, user.id))
    return results


@router.post("/import/daily-assignees", response_model=ImportResult)
async def import_daily_assignees_file(
    daily_file: UploadFile = File(..., description="Ежедневная выгрузка (Табельный/ФИО/Должность/Участок/Прораб)"),
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
) -> ImportResult:
    """Упрощённый ежедневный импорт: один Excel → поиск сотрудника по табельному,
    обновление ФИО/должности и создание/обновление закрепления на открытый период."""
    head = await daily_file.read(4)
    await daily_file.seek(0)
    if head != b"PK\x03\x04":
        raise HTTPException(status_code=400, detail="Файл не является Excel (.xlsx)")
    # Проверка размера файла — защита от zip-bomb и исчерпания памяти
    max_bytes = settings.max_upload_mb * 1024 * 1024
    content = await daily_file.read(max_bytes + 1)
    await daily_file.seek(0)
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Размер файла превышает {settings.max_upload_mb} МБ",
        )
    files_dir = settings.files_path
    files_dir.mkdir(parents=True, exist_ok=True)
    dest = files_dir / "Ежедневная_выгрузка.xlsx"
    with dest.open("wb") as out:
        out.write(content)
    org, period = ensure_org_by_id(db, user.organization_id)
    return import_daily_assignees(db, dest, org, period, user.id)


@router.post("/import/tariff-grid", response_model=list[ImportResult])
async def import_tariff_grid_file(
    grid_file: UploadFile = File(..., description="Сводная_тарифная_сетка.xlsx"),
    user: User = Depends(require_roles(UserRole.admin_op)),
    db: Session = Depends(get_db),
) -> list[ImportResult]:
    """Загрузка тарифной сетки (мин/макс ЧТС по должности и гражданству). Только ADMIN-OP."""
    if not grid_file.filename:
        raise HTTPException(status_code=400, detail="Файл не выбран")
    org, _period = ensure_org_by_id(db, user.organization_id)
    files_dir = settings.files_path
    files_dir.mkdir(parents=True, exist_ok=True)
    max_bytes = settings.max_upload_mb * 1024 * 1024
    head = await grid_file.read(4)
    await grid_file.seek(0)
    if head != b"PK\x03\x04":
        raise HTTPException(status_code=400, detail="Файл не является Excel (.xlsx)")
    content = await grid_file.read(max_bytes + 1)
    await grid_file.seek(0)
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Размер превышает {settings.max_upload_mb} МБ")
    dest = files_dir / "Сводная_тарифная_сетка.xlsx"
    with dest.open("wb") as out:
        shutil.copyfileobj(grid_file.file, out)
    result = import_tariff_grid(db, dest, org.id, user.id)
    return [result]


@router.get("/tariff-grid", response_model=list[TariffGridOut])
def list_tariff_grid(
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
) -> list[TariffGridOut]:
    """Список тарифной сетки (для проверки после импорта)."""
    rows = (
        db.query(TariffGrid)
        .order_by(TariffGrid.citizenship, TariffGrid.position)
        .limit(2000)
        .all()
    )
    return [
        TariffGridOut(position=r.position, citizenship=r.citizenship, min_rate=r.min_rate, max_rate=r.max_rate)
        for r in rows
    ]


@router.get("/assignments")
def list_assignments(
    evaluate: bool | None = None,
    awaiting_primary: bool | None = None,
    q: str | None = None,
    limit: int = 2000,
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
):
    _, period = ensure_org_by_id(db, user.organization_id)
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
            "position_fact": a.position_fact,
            "evaluate": a.evaluate,
            "primary_fio": p.fio if p else None,
            "primary_tab": p.tab_no if p else None,
            "primary_role": p.role.value if p else None,
            "primary_user_id": a.primary_user_id,
            "dual_enabled": a.dual_enabled,
            "secondary_user_id": a.secondary_user_id,
            "worker_status": a.worker_status,
            "version": a.version,
        }
        for a, e, p in rows
    ]


@router.post("/assignments/bulk")
@router.post("/assignment-bulk")
def bulk_assignments(
    body: BulkAssignmentsIn,
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
):
    """Массово: закрепить за прорабом/мастером и/или отправить/отозвать с оценки."""
    if body.primary_user_id is None and body.evaluate is None:
        raise HTTPException(status_code=400, detail="Укажите primary_user_id и/или evaluate")

    _, period = ensure_org_by_id(db, user.organization_id)

    primary: User | None = None
    if body.primary_user_id is not None:
        primary = db.get(User, body.primary_user_id)
        if (
            not primary
            or primary.organization_id != user.organization_id
            or primary.role not in (UserRole.master, UserRole.foreman)
        ):
            raise HTTPException(status_code=400, detail="Нужен мастер или прораб этой организации")
        if primary.status != UserStatus.active:
            raise HTTPException(status_code=400, detail="Оценщик отключён")

    updated = 0
    errors: list[str] = []
    changes: list[tuple[int, dict]] = []

    for aid in body.assignment_ids:
        asg = db.get(Assignment, aid)
        if (
            not asg
            or asg.organization_id != user.organization_id
            or asg.period_id != period.id
        ):
            errors.append(f"id={aid}: не найден в текущем периоде")
            continue
        change: dict = {}
        if body.primary_user_id is not None:
            asg.primary_user_id = body.primary_user_id
            change["primary_user_id"] = body.primary_user_id
        if body.evaluate is not None:
            if body.evaluate and not asg.primary_user_id:
                errors.append(f"id={aid}: нельзя отправить без закреплённого оценщика")
                continue
            asg.evaluate = bool(body.evaluate)
            change["evaluate"] = body.evaluate
        if asg.evaluate and not asg.primary_user_id:
            errors.append(f"id={aid}: evaluate без primary")
            continue
        asg.version = (asg.version or 1) + 1
        change["version"] = asg.version
        changes.append((aid, change))
        updated += 1

    if updated:
        emit_event(
            db,
            organization_id=user.organization_id,
            actor_user_id=user.id,
            entity_type="assignment",
            entity_id=None,
            action="bulk_updated",
            payload={
                "count": updated,
                "primary_user_id": body.primary_user_id,
                "evaluate": body.evaluate,
                "assignment_ids": [c[0] for c in changes],
            },
        )
        db.commit()
    else:
        db.rollback()

    return {
        "ok": True,
        "updated": updated,
        "errors": errors[:30],
        "primary_fio": primary.fio if primary else None,
    }


@router.patch("/assignments/{assignment_id}")
def patch_assignment(
    assignment_id: int,
    body: AssignPrimaryIn,
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
):
    asg = get_org_object(db, Assignment, assignment_id, user)
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


@router.get("/second-evaluation")
def second_evaluation(
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
):
    """Сотрудники периода со статусами 1-го и 2-го оценщика (вкладка «Вторая оценка»)."""
    _, period = ensure_org_by_id(db, user.organization_id)
    rows = (
        db.query(Assignment, Employee)
        .join(Employee, Employee.id == Assignment.employee_id)
        .filter(Assignment.period_id == period.id)
        .order_by(Employee.fio)
        .all()
    )
    primary_ids = {a.primary_user_id for a, _e in rows if a.primary_user_id}
    secondary_ids = {a.secondary_user_id for a, _e in rows if a.secondary_user_id}
    user_ids = primary_ids | secondary_ids
    names = {
        u.id: u.fio
        for u in db.query(User).filter(User.id.in_(user_ids)).all()
    } if user_ids else {}

    # Статусы анкет по всем закреплениям периода (с учётом заместителей)
    evals = (
        db.query(Evaluation)
        .join(Assignment, Assignment.id == Evaluation.assignment_id)
        .filter(Assignment.period_id == period.id)
        .all()
    )
    eval_by_asg: dict[int, list[Evaluation]] = {}
    for ev in evals:
        eval_by_asg.setdefault(ev.assignment_id, []).append(ev)

    def _status_for(assignment: Assignment, original_uid: int | None) -> str:
        if not original_uid:
            return "none"
        cover = covering_evaluator_ids(
            db,
            organization_id=user.organization_id,
            period_id=period.id,
            original_user_id=original_uid,
        )
        best: EvaluationStatus | None = None
        for ev in eval_by_asg.get(assignment.id, []):
            if ev.evaluator_id not in cover:
                continue
            if ev.status == EvaluationStatus.submitted:
                return "submitted"
            if ev.status == EvaluationStatus.draft:
                best = EvaluationStatus.draft
        if best == EvaluationStatus.draft:
            return "draft"
        return "none"

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
            "primary_user_id": a.primary_user_id,
            "primary_fio": names.get(a.primary_user_id),
            "primary_eval_status": _status_for(a, a.primary_user_id),
            "dual_enabled": a.dual_enabled,
            "secondary_user_id": a.secondary_user_id,
            "secondary_fio": names.get(a.secondary_user_id),
            "secondary_eval_status": _status_for(a, a.secondary_user_id),
            "version": a.version,
        }
        for a, e in rows
    ]


@router.post("/second-evaluation/assign")
def assign_secondary(
    body: SecondAssignIn,
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
):
    """Назначить 2-го оценщика (только начальник участка, только своего участка) или снять его."""
    _, period = ensure_org_by_id(db, user.organization_id)

    chief: User | None = None
    if body.secondary_user_id is not None:
        chief = db.get(User, body.secondary_user_id)
        if not chief or chief.organization_id != user.organization_id:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        if chief.role != UserRole.site_chief:
            raise HTTPException(
                status_code=400,
                detail="2-м оценщиком может быть только начальник участка",
            )
        if chief.status != UserStatus.active:
            raise HTTPException(status_code=400, detail="Начальник участка отключён")
        if not chief.site_name:
            raise HTTPException(
                status_code=400,
                detail=f"У {chief.fio} не указан участок — заполните в «Настройках»",
            )

    updated = 0
    errors: list[str] = []
    for aid in body.assignment_ids:
        asg = db.get(Assignment, aid)
        if not asg or asg.organization_id != user.organization_id or asg.period_id != period.id:
            errors.append(f"id={aid}: закрепление не найдено")
            continue
        emp = db.get(Employee, asg.employee_id)
        label = emp.fio if emp else f"id={aid}"
        try:
            if chief is not None:
                if not asg.evaluate:
                    errors.append(f"{label}: сотрудник не на оценке (evaluate=нет)")
                    continue
                if not asg.primary_user_id:
                    errors.append(f"{label}: сначала назначьте 1-го оценщика")
                    continue
                if not asg.site_name or nf(asg.site_name) != nf(chief.site_name):
                    errors.append(
                        f"{label}: участок «{asg.site_name or '—'}» ≠ участок начальника «{chief.site_name}»"
                    )
                    continue
                if asg.primary_user_id == chief.id:
                    errors.append(f"{label}: 1-й и 2-й оценщик совпадают")
                    continue
                asg.secondary_user_id = chief.id
                asg.dual_enabled = True
            else:
                if not asg.secondary_user_id:
                    continue  # и так без 2-го — не считаем ошибкой
                asg.secondary_user_id = None
                asg.dual_enabled = False
            asg.version = (asg.version or 1) + 1
            updated += 1
        except Exception as e:
            db.rollback()
            errors.append(f"{label}: ошибка при обработке — {e}")

    if updated:
        emit_event(
            db,
            organization_id=user.organization_id,
            actor_user_id=user.id,
            entity_type="assignment",
            entity_id=None,
            action="secondary_assigned" if chief else "secondary_removed",
            payload={
                "secondary_user_id": body.secondary_user_id,
                "count": updated,
                "assignment_ids": body.assignment_ids[:50],
            },
        )
        db.commit()
    else:
        db.rollback()

    return {
        "ok": True,
        "updated": updated,
        "errors": errors[:30],
        "secondary_fio": chief.fio if chief else None,
    }


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
    existing_open = (
        db.query(UrgentRequest)
        .filter(
            UrgentRequest.organization_id == user.organization_id,
            UrgentRequest.employee_id == emp.id,
            UrgentRequest.status == UrgentStatus.open,
        )
        .first()
    )
    if existing_open:
        raise HTTPException(
            status_code=400,
            detail=f"Уже есть открытая срочная №{existing_open.id} на этого сотрудника — закройте её или дождитесь сдачи",
        )
    ur = UrgentRequest(
        organization_id=user.organization_id,
        employee_id=emp.id,
        created_by_user_id=user.id,
        comment=body.comment,
        status="open",
    )
    db.add(ur)
    db.flush()
    for uid in dict.fromkeys(body.evaluator_user_ids):
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
    ur = get_org_object(db, UrgentRequest, urgent_id, user)
    ur.status = UrgentStatus.closed
    ur.closed_at = datetime.now(timezone.utc).replace(tzinfo=None)
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
        evals = (
            db.query(UrgentEvaluator, User)
            .outerjoin(User, User.id == UrgentEvaluator.user_id)
            .filter(UrgentEvaluator.urgent_request_id == ur.id)
            .all()
        )
        out.append(
            {
                "id": ur.id,
                "status": ur.status,
                "comment": ur.comment,
                "employee_id": emp.id,
                "tab_no": emp.tab_no,
                "fio": emp.fio,
                "evaluator_ids": [e.user_id for e, _u in evals],
                "evaluator_names": [
                    (
                        f"{u.fio} ({'мастер' if (u.role == UserRole.master or str(u.role) == 'master') else 'прораб'})"
                        if u
                        else f"user#{e.user_id}"
                    )
                    for e, u in evals
                ],
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
    _, period = ensure_org_by_id(db, user.organization_id)
    orig = db.get(User, body.original_user_id)
    sub = db.get(User, body.substitute_user_id)
    if not orig or not sub:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if orig.id == sub.id:
        raise HTTPException(status_code=400, detail="Нельзя замещать самого себя")
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
    d = get_org_object(db, Delegation, delegation_id, user)
    d.is_active = False
    db.commit()
    return {"ok": True}


@router.get("/users")
def list_users(
    role: UserRole | None = None,
    all: bool = False,
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
):
    q = db.query(User).filter(User.organization_id == user.organization_id)
    if not all:
        q = q.filter(User.status == UserStatus.active)
    if role:
        q = q.filter(User.role == role)
    return [
        {
            "id": u.id,
            "tab_no": u.tab_no,
            "fio": u.fio,
            "role": u.role.value,
            "site_code": u.site_code,
            "site_name": u.site_name,
            "status": u.status,
            "last_login_at": u.last_login_at,
        }
        for u in q.order_by(User.fio).all()
    ]


@router.patch("/users/{user_id}")
def patch_user(
    user_id: int,
    body: UserPatchIn,
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
):
    """Правка пользователя из вкладки «Настройки»: роль, участок, статус, пароль."""
    target = db.get(User, user_id)
    if not target or target.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    # Запрет эскалации: admin_op не может менять системного администратора (роль, статус, пароль).
    if user.role == UserRole.admin_op and target.role == UserRole.admin:
        raise HTTPException(
            status_code=403,
            detail="Администрация ОП не может изменять системного администратора",
        )

    data = body.model_dump(exclude_unset=True)
    if target.id == user.id and (
        ("role" in data and data["role"] != target.role)
        or ("status" in data and data["status"] != target.status)
    ):
        raise HTTPException(
            status_code=400,
            detail="Нельзя менять собственную роль или статус — попросите другого администратора",
        )

    if "role" in data and data["role"] is not None:
        if user.role == UserRole.admin_op and data["role"] == UserRole.admin:
            raise HTTPException(
                status_code=403,
                detail="Администрация ОП не может назначать роль системного админа",
            )
        target.role = data["role"]
    if "site_code" in data:
        target.site_code = (data["site_code"] or "").strip() or None
    if "site_name" in data:
        target.site_name = (data["site_name"] or "").strip() or None
    if "status" in data and data["status"]:
        target.status = data["status"].strip()
    if "password" in data and data["password"]:
        target.password_hash = hash_password(data["password"].strip())
        # F03 FIX: увеличиваем token_version — старые токены отзываются
        target.token_version = (target.token_version or 0) + 1
        target.must_change_password = True

    emit_event(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        entity_type="user",
        entity_id=target.id,
        action="updated",
        payload={k: ("***" if k == "password" else v) for k, v in data.items()},
    )
    db.commit()
    return {
        "ok": True,
        "user": {
            "id": target.id,
            "tab_no": target.tab_no,
            "fio": target.fio,
            "role": target.role.value,
            "site_code": target.site_code,
            "site_name": target.site_name,
            "status": target.status,
        },
    }


@router.post("/users")
def create_user(
    body: UserCreateIn,
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
):
    """Создать пользователя вручную (кнопка «Создать сотрудника» в «Настройках»)."""
    tab_no = body.tab_no.strip()
    fio = body.fio.strip()
    if not tab_no or not fio:
        raise HTTPException(status_code=400, detail="Укажите табельный номер и ФИО")
    exists = (
        db.query(User)
        .filter(User.organization_id == user.organization_id, User.tab_no == tab_no)
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail=f"Табельный {tab_no} уже занят ({exists.fio})")
    if user.role == UserRole.admin_op and body.role == UserRole.admin:
        raise HTTPException(
            status_code=403,
            detail="Администрация ОП не может создавать системного админа",
        )
    # admin_op может создавать только master/foreman/site_chief — предотвращает privilege creep
    if user.role == UserRole.admin_op and body.role not in (
        UserRole.master,
        UserRole.foreman,
        UserRole.site_chief,
    ):
        raise HTTPException(
            status_code=403,
            detail="Администрация ОП может создавать только мастеров, прорабов и начальников участков",
        )
    target = User(
        organization_id=user.organization_id,
        tab_no=tab_no,
        fio=fio,
        role=body.role,
        site_code=(body.site_code or "").strip() or None,
        site_name=(body.site_name or "").strip() or None,
        status=body.status.strip() or UserStatus.active.value,
        password_hash=hash_password(body.password.strip()),
    )
    db.add(target)
    db.flush()
    emit_event(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        entity_type="user",
        entity_id=target.id,
        action="created",
        payload={"tab_no": tab_no, "role": body.role.value},
    )
    db.commit()
    return {"ok": True, "user_id": target.id}


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
    out: list[dict] = []
    for e in query.order_by(Employee.fio).limit(limit).all():
        t_min, t_max = grid_bounds(db, e.position_1c, e.citizenship)
        out.append(
            {
                "id": e.id,
                "tab_no": e.tab_no,
                "fio": e.fio,
                "position_1c": e.position_1c,
                "is_candidate": e.is_candidate,
                "hire_date": e.hire_date,
                "citizenship": e.citizenship,
                "hourly_rate": e.hourly_rate,
                "rate_updated_at": e.rate_updated_at,
                "rate_last_raised": e.rate_last_raised,
                "is_rate_expired": is_rate_expired(e.rate_last_raised),
                "tariff_min": t_min,
                "tariff_max": t_max,
            }
        )
    return out


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


@router.patch("/employees/{employee_id}")
def patch_employee(
    employee_id: int,
    body: EmployeePatchIn,
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
):
    """Правка ЧТС и даты последнего поднятия. При изменении ЧТС дата ставится автоматически = сегодня."""
    emp = get_org_object(db, Employee, employee_id, user)
    changed: dict = {}
    if body.hourly_rate is not None:
        new_rate = round(float(body.hourly_rate), 2)
        if new_rate != (emp.hourly_rate or 0.0):
            emp.hourly_rate = new_rate
            # Подняли ставку — дата последнего повышения = сегодня.
            emp.rate_last_raised = date.today()
            emp.rate_updated_at = date.today()
            changed["hourly_rate"] = new_rate
            changed["rate_last_raised"] = emp.rate_last_raised.isoformat()
    if body.rate_last_raised is not None:
        emp.rate_last_raised = body.rate_last_raised
        changed["rate_last_raised"] = body.rate_last_raised.isoformat()
    if not changed:
        raise HTTPException(status_code=400, detail="Нет изменений для сохранения")
    emit_event(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        entity_type="employee",
        entity_id=emp.id,
        action="rate_updated",
        payload=changed,
    )
    db.commit()
    t_min, t_max = grid_bounds(db, emp.position_1c, emp.citizenship)
    return {
        "id": emp.id,
        "tab_no": emp.tab_no,
        "fio": emp.fio,
        "position_1c": emp.position_1c,
        "is_candidate": emp.is_candidate,
        "hire_date": emp.hire_date,
        "citizenship": emp.citizenship,
        "hourly_rate": emp.hourly_rate,
        "rate_updated_at": emp.rate_updated_at,
        "rate_last_raised": emp.rate_last_raised,
        "is_rate_expired": is_rate_expired(emp.rate_last_raised),
        "tariff_min": t_min,
        "tariff_max": t_max,
    }


@router.post("/employees/formalize-candidate")
def formalize_candidate(
    body: FormalizeCandidateIn,
    user: User = Depends(require_roles(UserRole.admin, UserRole.admin_op)),
    db: Session = Depends(get_db),
):
    emp = get_org_object(db, Employee, body.employee_id, user)
    if not emp.is_candidate:
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
    t = get_org_object(db, ListTicket, ticket_id, user)
    if body.status is not None:
        allowed_statuses = {s.value for s in TicketStatus}
        if body.status not in allowed_statuses:
            raise HTTPException(status_code=400, detail="Неверный статус")
        t.status = body.status
    if body.admin_note is not None:
        t.admin_note = body.admin_note.strip() or None
        if t.admin_note and t.status == TicketStatus.new:
            t.status = TicketStatus.in_progress
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
    _, period = ensure_org_by_id(db, user.organization_id)
    return escalation_report(db, organization_id=user.organization_id, period_id=period.id)
