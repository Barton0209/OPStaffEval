from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.models import (
    Assignment,
    Employee,
    EvaluationPeriod,
    Organization,
    User,
    UserRole,
)
from app.schemas import ImportResult
from app.security import hash_password
from app.services.events import emit_event


def dig(tab: str | None) -> str:
    if not tab:
        return ""
    m = re.search(r"(\d{5,})", str(tab).upper().replace(" ", ""))
    return m.group(1) if m else ""


def nf(value: str | None) -> str:
    return " ".join(str(value or "").strip().upper().split())


def parse_date(value) -> date | None:
    if value is None or value == "" or value == "-":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s[:19], fmt).date()
        except ValueError:
            continue
    return None


ROLE_MAP = {
    "мастер": UserRole.master,
    "производитель работ": UserRole.foreman,
    "начальник участка": UserRole.site_chief,
    "admin": UserRole.admin,
    "admin_op": UserRole.admin_op,
    "администрация_оп": UserRole.admin_op,
    "администрация оп": UserRole.admin_op,
}


def map_role(raw: str) -> UserRole | None:
    return ROLE_MAP.get(str(raw or "").strip().lower())


def ensure_org_and_period(db: Session, org_code: str, org_name: str) -> tuple[Organization, EvaluationPeriod]:
    org = db.query(Organization).filter(Organization.code == org_code).first()
    if not org:
        org = Organization(code=org_code, name=org_name)
        db.add(org)
        db.flush()
    period = (
        db.query(EvaluationPeriod)
        .filter(EvaluationPeriod.organization_id == org.id, EvaluationPeriod.is_open.is_(True))
        .order_by(EvaluationPeriod.id.desc())
        .first()
    )
    if not period:
        period = EvaluationPeriod(
            organization_id=org.id,
            code="2026-H2",
            title="Полугодие 2026-H2",
            is_open=True,
        )
        db.add(period)
        db.flush()
    return org, period


def import_base(db: Session, path: Path, org: Organization, actor_id: int | None = None) -> ImportResult:
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    added = updated = skipped = 0
    errors: list[str] = []
    for i, row in enumerate(ws.iter_rows(values_only=True), 1):
        if i == 1:
            continue
        if not row or not row[0]:
            continue
        tab_no = str(row[0]).strip()
        fio = str(row[1] or "").strip()
        if not fio:
            skipped += 1
            continue
        is_candidate = tab_no.lower() == "кандидат" or "андид" in tab_no.lower()
        if is_candidate:
            # unique storage key while UI/export can show as candidate
            storage_tab = f"КАНД-{nf(fio)[:40]}" if fio else f"КАНД-R{i}"
            emp = (
                db.query(Employee)
                .filter(Employee.organization_id == org.id, Employee.tab_no == storage_tab)
                .first()
            )
            fields = {
                "fio": fio,
                "territory": str(row[3] or "").strip() or None if len(row) > 3 else None,
                "department_1c": str(row[4] or "").strip() or None if len(row) > 4 else None,
                "position_1c": str(row[5] or "").strip() or None if len(row) > 5 else None,
                "hire_date": parse_date(row[6]) if len(row) > 6 else None,
                "state": str(row[7] or "").strip() or None if len(row) > 7 else None,
                "experience_text": str(row[8] or "").strip() or None if len(row) > 8 else None,
                "hourly_rate": float(row[9]) if len(row) > 9 and row[9] not in (None, "") else None,
                "rate_updated_at": parse_date(row[10]) if len(row) > 10 else None,
                "is_candidate": True,
            }
            tab_no = storage_tab
        else:
            emp = (
                db.query(Employee)
                .filter(Employee.organization_id == org.id, Employee.tab_no == tab_no)
                .first()
            )
            fields = {
                "fio": fio,
                "territory": str(row[3] or "").strip() or None if len(row) > 3 else None,
                "department_1c": str(row[4] or "").strip() or None if len(row) > 4 else None,
                "position_1c": str(row[5] or "").strip() or None if len(row) > 5 else None,
                "hire_date": parse_date(row[6]) if len(row) > 6 else None,
                "state": str(row[7] or "").strip() or None if len(row) > 7 else None,
                "experience_text": str(row[8] or "").strip() or None if len(row) > 8 else None,
                "hourly_rate": float(row[9]) if len(row) > 9 and row[9] not in (None, "") else None,
                "rate_updated_at": parse_date(row[10]) if len(row) > 10 else None,
                "is_candidate": False,
            }
        try:
            if emp:
                for k, v in fields.items():
                    setattr(emp, k, v)
                updated += 1
            else:
                db.add(Employee(organization_id=org.id, tab_no=tab_no, **fields))
                added += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"R{i} {tab_no}: {exc}")
            skipped += 1
    wb.close()
    emit_event(
        db,
        organization_id=org.id,
        actor_user_id=actor_id,
        entity_type="import",
        entity_id=None,
        action="import_base",
        payload={"added": added, "updated": updated, "file": path.name},
    )
    db.commit()
    return ImportResult(source=path.name, added=added, updated=updated, skipped=skipped, errors=errors)


def import_users(db: Session, path: Path, org: Organization, actor_id: int | None = None) -> ImportResult:
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    added = updated = skipped = 0
    errors: list[str] = []
    seen_tabs: set[str] = set()
    for i, row in enumerate(ws.iter_rows(values_only=True), 1):
        if i == 1:
            continue
        if not row or not row[0]:
            continue
        tab_no = str(row[0]).strip()
        fio = str(row[1] or "").strip()
        if not tab_no or tab_no.replace("-", "").replace(" ", "") == "" or set(tab_no) <= {"-", " "}:
            errors.append(f"R{i}: пустой/битый tab_no ({tab_no!r})")
            skipped += 1
            continue
        if tab_no in seen_tabs:
            errors.append(f"R{i} {tab_no}: дубль в файле, пропуск")
            skipped += 1
            continue
        seen_tabs.add(tab_no)
        role = map_role(str(row[2] or ""))
        if not role:
            errors.append(f"R{i} {tab_no}: неизвестная роль {row[2]}")
            skipped += 1
            continue
        status = str(row[5] or "Активен").strip() or "Активен"
        password = str(row[6] or f"K{dig(tab_no) or 'temp'}").strip() or "ChangeMe123"
        user = db.query(User).filter(User.organization_id == org.id, User.tab_no == tab_no).first()
        try:
            if user:
                user.fio = fio
                user.role = role
                user.site_code = str(row[3] or "").strip() or None
                user.site_name = str(row[4] or "").strip() or None
                user.status = status
                updated += 1
            else:
                db.add(
                    User(
                        organization_id=org.id,
                        tab_no=tab_no,
                        fio=fio,
                        role=role,
                        site_code=str(row[3] or "").strip() or None,
                        site_name=str(row[4] or "").strip() or None,
                        status=status,
                        password_hash=hash_password(password),
                    )
                )
                db.flush()
                added += 1
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            # re-ensure org session objects after rollback is messy; use nested try
            errors.append(f"R{i} {tab_no}: {exc}")
            skipped += 1
            return ImportResult(source=path.name, added=added, updated=updated, skipped=skipped, errors=errors)
    wb.close()
    admin = (
        db.query(User)
        .filter(User.organization_id == org.id, User.role.in_([UserRole.admin, UserRole.admin_op]))
        .first()
    )
    if not admin:
        db.add(
            User(
                organization_id=org.id,
                tab_no="ADMIN-OP",
                fio="Администрация ОП",
                role=UserRole.admin_op,
                status="Активен",
                password_hash=hash_password("AdminOP2026"),
            )
        )
        added += 1
    emit_event(
        db,
        organization_id=org.id,
        actor_user_id=actor_id,
        entity_type="import",
        entity_id=None,
        action="import_users",
        payload={"added": added, "updated": updated, "file": path.name},
    )
    db.commit()
    return ImportResult(source=path.name, added=added, updated=updated, skipped=skipped, errors=errors)


def resolve_assignment_registry_path(files_dir: Path) -> Path | None:
    """Файл закреплений сотрудников за оценщиками (бывш. «карнет»)."""
    candidates = [
        files_dir / "03_Реестр_закрепления.xlsx",
        files_dir / "03_Карнет.xlsx",
        files_dir / "03_Карнет_v2.xlsx",
        files_dir / "03_Карнет_ШАБЛОН.xlsx",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _pick_registry_sheet(wb):
    for name in ("Реестр_закрепления", "Карнет"):
        if name in wb.sheetnames:
            return wb[name]
    return wb.active


def import_carnet(db: Session, path: Path, org: Organization, period: EvaluationPeriod, actor_id: int | None = None) -> ImportResult:
    """Импорт реестра закреплений (assignments). Имя функции сохранено для совместимости."""
    users_by_tab = {
        u.tab_no: u for u in db.query(User).filter(User.organization_id == org.id).all()
    }
    users_by_fio = {nf(u.fio): u for u in users_by_tab.values()}
    emps_by_tab = {
        e.tab_no: e
        for e in db.query(Employee).filter(Employee.organization_id == org.id, Employee.is_candidate.is_(False)).all()
    }
    # candidates keyed by fio
    candidates = {
        nf(e.fio): e
        for e in db.query(Employee).filter(Employee.organization_id == org.id, Employee.is_candidate.is_(True)).all()
    }

    wb = load_workbook(path, read_only=True, data_only=True)
    ws = _pick_registry_sheet(wb)
    added = updated = skipped = 0
    errors: list[str] = []

    for i, row in enumerate(ws.iter_rows(values_only=True), 1):
        if i == 1:
            continue
        if not row or not row[0]:
            continue
        # skip hint row if present
        if str(row[0]).strip().lower() in {"tab_no"}:
            continue
        tab_no = str(row[0]).strip()
        fio = str(row[1] or "").strip()
        site_code = str(row[2] or "").strip() or None
        site_name = str(row[3] or "").strip() or None
        position_fact = str(row[4] or "").strip() or None
        primary_tab = str(row[5] or "").strip() if len(row) > 5 and row[5] else ""
        primary_fio = str(row[6] or "").strip() if len(row) > 6 and row[6] else ""
        worker_status = str(row[7] or "").strip() if len(row) > 7 else ""
        shift_start = parse_date(row[8]) if len(row) > 8 else None
        last_score = None
        if len(row) > 9 and row[9] not in (None, ""):
            try:
                last_score = float(row[9])
            except (TypeError, ValueError):
                last_score = None
        evaluate_raw = str(row[10] or "").strip().lower() if len(row) > 10 else ""
        dual_raw = str(row[11] or "no").strip().lower() if len(row) > 11 else "no"
        secondary_tab = str(row[12] or "").strip() if len(row) > 12 and row[12] else ""
        secondary_fio = str(row[13] or "").strip() if len(row) > 13 and row[13] else ""

        is_candidate = tab_no.lower() == "кандидат" or "андид" in tab_no.lower()
        if is_candidate:
            storage_tab = f"КАНД-{nf(fio)[:40]}" if fio else f"КАНД-R{i}"
            emp = candidates.get(nf(fio)) or (
                db.query(Employee)
                .filter(Employee.organization_id == org.id, Employee.tab_no == storage_tab)
                .first()
            )
            if not emp:
                emp = Employee(
                    organization_id=org.id,
                    tab_no=storage_tab,
                    fio=fio,
                    is_candidate=True,
                    position_1c=position_fact,
                )
                db.add(emp)
                db.flush()
                candidates[nf(fio)] = emp
            evaluate = False
            primary_user = None
            secondary_user = None
            dual_enabled = False
        else:
            emp = emps_by_tab.get(tab_no)
            if not emp:
                # create stub from registry if missing in base
                emp = Employee(
                    organization_id=org.id,
                    tab_no=tab_no,
                    fio=fio,
                    position_1c=position_fact,
                    is_candidate=False,
                )
                db.add(emp)
                db.flush()
                emps_by_tab[tab_no] = emp
            elif nf(emp.fio) != nf(fio):
                errors.append(f"R{i} {tab_no}: ФИО реестр≠база ({fio} / {emp.fio})")

            primary_user = users_by_tab.get(primary_tab) if primary_tab else None
            if not primary_user and primary_fio:
                primary_user = users_by_fio.get(nf(primary_fio))
            if primary_user and primary_user.role not in (UserRole.master, UserRole.foreman):
                errors.append(f"R{i} {tab_no}: primary роль {primary_user.role.value}")
                primary_user = None

            secondary_user = users_by_tab.get(secondary_tab) if secondary_tab else None
            if not secondary_user and secondary_fio:
                secondary_user = users_by_fio.get(nf(secondary_fio))

            dual_enabled = dual_raw in {"yes", "1", "true", "да"}
            if dual_enabled and not secondary_user:
                dual_enabled = False
                errors.append(f"R{i} {tab_no}: dual=yes без secondary")

            if evaluate_raw in {"yes", "1", "true", "да"}:
                evaluate = primary_user is not None
            elif evaluate_raw in {"no", "0", "false", "нет"}:
                evaluate = False
            else:
                evaluate = primary_user is not None and worker_status in {"Работает", "На межвахте"}

        asg = (
            db.query(Assignment)
            .filter(Assignment.period_id == period.id, Assignment.employee_id == emp.id)
            .first()
        )
        payload = {
            "site_code": site_code,
            "site_name": site_name,
            "position_fact": position_fact,
            "worker_status": "Кандидат" if is_candidate else (worker_status or None),
            "shift_start": shift_start,
            "last_final_score": last_score,
            "evaluate": evaluate,
            "primary_user_id": primary_user.id if primary_user else None,
            "dual_enabled": dual_enabled,
            "secondary_user_id": secondary_user.id if secondary_user else None,
        }
        try:
            if asg:
                for k, v in payload.items():
                    setattr(asg, k, v)
                asg.version = (asg.version or 1) + 1
                updated += 1
            else:
                db.add(
                    Assignment(
                        organization_id=org.id,
                        period_id=period.id,
                        employee_id=emp.id,
                        **payload,
                    )
                )
                added += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"R{i} {tab_no}: {exc}")
            skipped += 1

    wb.close()
    emit_event(
        db,
        organization_id=org.id,
        actor_user_id=actor_id,
        entity_type="import",
        entity_id=period.id,
        action="import_assignment_registry",
        payload={"added": added, "updated": updated, "file": path.name},
    )
    db.commit()
    return ImportResult(source=path.name, added=added, updated=updated, skipped=skipped, errors=errors[:50])
