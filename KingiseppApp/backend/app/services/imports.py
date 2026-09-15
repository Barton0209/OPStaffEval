from __future__ import annotations

import logging
import re
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.models import (
    Assignment,
    Department,
    Employee,
    EvaluationPeriod,
    FiredEmployee,
    GroupOfUsers,
    ImportLog,
    Organization,
    RegistryImport,
    RegistryScore,
    TariffGrid,
    Territory,
    Transfer,
    User,
    UserStatus,
    UserTerritoryMapping,
    UserRole,
)
from app.services.tariff import citizenship_group

logger = logging.getLogger(__name__)
from app.schemas import ImportResult
from app.security import generate_temporary_password, hash_password
from app.services.events import emit_event


# Максимально допустимое соотношение сжатого/несжатого размера (zip-bomb защита).
# Excel (.xlsx/.xlsb) — zip-архивы; если ratio > 100, файл может исчерпать память.
MAX_ZIP_RATIO = 100


def _check_zip_bomb(path: Path) -> None:
    """Проверяет Excel-файл на zip-bomb атаку. Выбрасывает HTTPException при обнаружении."""
    try:
        with zipfile.ZipFile(path) as zf:
            for info in zf.infolist():
                if info.compress_size > 0 and info.file_size > 0:
                    ratio = info.file_size / info.compress_size
                    if ratio > MAX_ZIP_RATIO:
                        logger.warning(
                            "Zip-bomb detected: %s ratio=%.1f (limit=%d)",
                            info.filename, ratio, MAX_ZIP_RATIO,
                        )
                        raise ValueError(
                            f"Файл содержит подозрительное сжатие ({info.filename}: ratio={ratio:.0f}x)"
                        )
    except ValueError:
        raise
    except Exception as e:
        logger.error("Error checking zip bomb for %s: %s", path, e)


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
    "руководство оп": UserRole.management_op,
    "линейный ит": UserRole.master,
    "линейный ит2": UserRole.foreman,
}

# Whitelist ролей, которые можно импортировать через Excel (безопасный импорт не повышает выше admin_op)
IMPORTABLE_ROLES: set[UserRole] = {
    UserRole.master,
    UserRole.foreman,
    UserRole.site_chief,
    UserRole.admin_op,
    UserRole.economist,
    UserRole.management_op,
    UserRole.cok_okit,
    UserRole.cok_adapt,
    UserRole.cok_otiz,
}

# Роли, которые НЕЛЬЗЯ создать/изменить через импорт
FORBIDDEN_IMPORT_ROLES: set[UserRole] = {UserRole.admin}


def map_role(raw: str) -> UserRole | None:
    return ROLE_MAP.get(str(raw or "").strip().lower())


def is_role_safe_for_import(role: UserRole) -> bool:
    """Проверяет, что роль не превышает допустимый уровень для импорта."""
    return role not in FORBIDDEN_IMPORT_ROLES


def ensure_org_and_period(db: Session, org_code: str, org_name: str) -> tuple[Organization, EvaluationPeriod]:
    org = db.query(Organization).filter(Organization.code == org_code).first()
    if not org:
        org = Organization(code=org_code, name=org_name)
        db.add(org)
        db.flush()
    return _ensure_period_for_org(db, org)


def ensure_org_by_id(db: Session, org_id: int) -> tuple[Organization, EvaluationPeriod]:
    """Получить организацию по ID и связанный период (F05 FIX для IDOR)."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        org = Organization(code=f"org-{org_id}", name=f"Организация {org_id}")
        db.add(org)
        db.flush()
    return _ensure_period_for_org(db, org)


def _default_period_code(today: date) -> tuple[str, str]:
    """Код и название периода по умолчанию: текущее полугодие (2026-H1 / 2026-H2)."""
    half = "H1" if today.month <= 6 else "H2"
    return f"{today.year}-{half}", f"Полугодие {today.year}-{half}"


def _ensure_period_for_org(db: Session, org: Organization) -> EvaluationPeriod:
    period = (
        db.query(EvaluationPeriod)
        .filter(EvaluationPeriod.organization_id == org.id, EvaluationPeriod.is_open.is_(True))
        .order_by(EvaluationPeriod.id.desc())
        .first()
    )
    if not period:
        code, title = _default_period_code(date.today())
        period = EvaluationPeriod(
            organization_id=org.id,
            code=code,
            title=title,
            is_open=True,
        )
        db.add(period)
        db.flush()
    return org, period


def import_base(db: Session, path: Path, org: Organization, actor_id: int | None = None) -> ImportResult:
    """Импорт 01_База_1С.xlsx — проверка на zip-bomb перед открытием."""
    _check_zip_bomb(path)
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
    """Импорт 02_Пользователи.xlsx — проверка на zip-bomb перед открытием.
    
    ВАЖНО: импорт НЕ может создать или изменить роль admin.
    admin_op не может повысить себя или других до admin через файл.
    """
    _check_zip_bomb(path)
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
        # F02 FIX: запрет ролей, которые нельзя импортировать
        if not is_role_safe_for_import(role):
            errors.append(f"R{i} {tab_no}: роль {role.value} запрещена для импорта (безопасность)")
            skipped += 1
            continue
        raw_status = str(row[5] or "Активен").strip() or "Активен"
        status = UserStatus.active if "актив" in raw_status.lower() else UserStatus.disabled
        # Пароль из Excel НЕ используется как дефолт: пустая ячейка => случайный
        # одноразовый пароль (пользователь обязан сменить при первом входе).
        raw_password = str(row[6] or "").strip()
        password = raw_password if raw_password else generate_temporary_password()
        user = db.query(User).filter(User.organization_id == org.id, User.tab_no == tab_no).first()
        try:
            # SAVEPOINT на строку: ошибка одной строки не откатывает весь импорт.
            with db.begin_nested():
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
            errors.append(f"R{i} {tab_no}: {exc}")
            skipped += 1
    wb.close()
    admin = (
        db.query(User)
        .filter(User.organization_id == org.id, User.role.in_([UserRole.admin, UserRole.admin_op]))
        .first()
    )
    if not admin:
        temp_pwd = generate_temporary_password()
        db.add(
            User(
                organization_id=org.id,
                tab_no="ADMIN-OP",
                fio="Администрация ОП",
                role=UserRole.admin_op,
                status=UserStatus.active,
                password_hash=hash_password(temp_pwd),
            )
        )
        logger.warning(
            "Создана учётная запись ADMIN-OP с временным паролем — смените пароль при первом входе",
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
    _check_zip_bomb(path)
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


# ---------- ЧТС (УД-список .xlsb) и тарифная сетка ----------


def _excel_date(value) -> date | None:
    """Дата из Excel: datetime, строка или серийный номер (например 46115)."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        try:
            serial = float(value)
        except (TypeError, ValueError):
            return None
        if serial > 20000:  # это серийный номер даты, а не год/число
            return date(1899, 12, 30) + timedelta(days=serial)
        return None
    if isinstance(value, str):
        return parse_date(value)
    return None


def _to_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if value != value:  # NaN
            return None
        return float(value)
    s = str(value).strip().replace(" ", "").replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _norm_tab(value) -> str:
    return str(value or "").strip().upper()


def import_ud_rates(db: Session, path: Path, org: Organization, actor_id: int | None = None) -> ImportResult:
    """Импорт ЧТС и даты последнего поднятия из УД-списка (.xlsb).

    Листы РОП/ИТР, колонки: «Табельный номер», «УД на сегодня», «Дата последнего изменения»,
    «Страна гражданства», «Фактическая должность». Обновляет только найденных сотрудников.
    """
    _check_zip_bomb(path)
    added = updated = skipped = 0
    errors: list[str] = []
    try:
        data = pd.read_excel(path, sheet_name=None, engine="pyxlsb", header=0)
    except Exception as exc:  # noqa: BLE001
        return ImportResult(source=path.name, added=0, updated=0, skipped=0, errors=[f"Не удалось прочитать .xlsb: {exc}"])

    employees = {
        e.tab_no: e for e in db.query(Employee).filter(Employee.organization_id == org.id).all()
    }
    by_dig: dict[str, Employee] = {}
    for e in employees.values():
        d = dig(e.tab_no)
        if d:
            by_dig.setdefault(d, e)

    for sheet_name, df in data.items():
        if df is None or df.empty:
            continue
        cols = {str(c).strip().lower(): c for c in df.columns}

        def _col(*names: str):
            for n in names:
                c = cols.get(n)
                if c is not None:
                    return c
            return None

        c_tab = _col("табельный номер", "табельныйномер", "таб. №")
        c_rate = _col("уд на сегодня", "чте", "ставка", "часовая тарифная ставка")
        c_raised = _col("дата последнего изменения", "дата последнего поднятия", "дата повышения")
        c_cit = _col("страна гражданства", "гражданство")
        c_pos = _col("фактическая должность", "должность", "профессия")
        if c_tab is None or c_rate is None:
            skipped += len(df)
            errors.append(f"Лист «{sheet_name}»: не найдены колонки табельного номера/УД — пропущен")
            continue
        for i, row in df.iterrows():
            try:
                tab_raw = row[c_tab]
                rate = _to_float(row[c_rate])
                if rate is None:
                    skipped += 1
                    continue
                tab_norm = _norm_tab(tab_raw)
                emp = employees.get(tab_norm)
                if emp is None and tab_raw is not None:
                    emp = by_dig.get(dig(str(tab_raw)))
                if emp is None:
                    skipped += 1
                    errors.append(f"{sheet_name} R{i + 2}: сотрудник {tab_raw!r} не найден в базе")
                    continue
                emp.hourly_rate = rate
                raised = _excel_date(row[c_raised]) if c_raised is not None else None
                if raised:
                    emp.rate_last_raised = raised
                    emp.rate_updated_at = raised  # обратная совместимость
                if c_cit is not None:
                    cit = row[c_cit]
                    if isinstance(cit, str) and cit.strip():
                        emp.citizenship = cit.strip()
                if c_pos is not None:
                    pos = row[c_pos]
                    if isinstance(pos, str) and pos.strip():
                        emp.position_1c = pos.strip()
                updated += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{sheet_name} R{i + 2}: {exc}")
                skipped += 1

    emit_event(
        db,
        organization_id=org.id,
        actor_user_id=actor_id,
        entity_type="import",
        entity_id=None,
        action="import_ud_rates",
        payload={"updated": updated, "file": path.name},
    )
    db.commit()
    return ImportResult(source=path.name, added=added, updated=updated, skipped=skipped, errors=errors[:50])


def import_tariff_grid(
    db: Session, path: Path, org_id: int, actor_id: int | None = None
) -> ImportResult:
    """Импорт тарифной сетки из Сводная_тарифная_сетка.xlsx (upsert по должность+гражданство).

    Берётся лист «Все данные» (или первый). Вилка по регионам сворачивается:
    min = минимальная из ненулевых «мин», max = максимальная из «макс».
    """
    _check_zip_bomb(path)
    added = updated = skipped = 0
    errors: list[str] = []
    try:
        wb = pd.ExcelFile(path, engine="openpyxl")
        sheets = wb.sheet_names
    except Exception as exc:  # noqa: BLE001
        return ImportResult(source=path.name, added=0, updated=0, skipped=0, errors=[f"Не удалось прочитать .xlsx: {exc}"])
    target = "Все данные" if "Все данные" in sheets else (sheets[0] if sheets else None)
    if not target:
        return ImportResult(source=path.name, added=0, updated=0, skipped=0, errors=["Файл без листов"])
    df = pd.read_excel(path, sheet_name=target, engine="openpyxl", header=0)
    if df is None or df.empty:
        return ImportResult(source=path.name, added=0, updated=0, skipped=0, errors=[f"Лист «{target}» пуст"])

    cols = {str(c).strip().lower(): c for c in df.columns}
    c_cit = next((cols[n] for n in ("гражданство",) if n in cols), None)
    c_pos = next((cols[n] for n in ("профессия", "должность") if n in cols), None)
    if c_cit is None or c_pos is None:
        return ImportResult(
            source=path.name, added=0, updated=0, skipped=0,
            errors=[f"Лист «{target}»: не найдены колонки Гражданство/Профессия"],
        )
    min_cols: list = []
    max_cols: list = []
    for name, col in cols.items():
        m = re.match(r"^(\d+)\s*регион\s*(мин|макс)$", name)
        if m:
            (min_cols if m.group(2) == "мин" else max_cols).append(col)

    for i, row in df.iterrows():
        pos = str(row[c_pos] or "").strip()
        if not pos:
            skipped += 1
            continue
        cit_raw = str(row[c_cit] or "").strip()
        group = citizenship_group(cit_raw) or cit_raw
        if not group:
            skipped += 1
            errors.append(f"R{i + 2}: не определено гражданство {cit_raw!r}")
            continue
        mins = [float(v) for v in (row[c] for c in min_cols) if _to_float(v) is not None and _to_float(v) > 0]
        maxes = [float(v) for v in (row[c] for c in max_cols) if _to_float(v) is not None and _to_float(v) > 0]
        if not mins and not maxes:
            skipped += 1
            continue
        min_rate = min(mins) if mins else 0.0
        max_rate = max(maxes) if maxes else 0.0
        row_obj = (
            db.query(TariffGrid)
            .filter(TariffGrid.position == pos, TariffGrid.citizenship == group)
            .first()
        )
        if row_obj:
            # Слияние: сохраняем минимальный «мин» и максимальный «макс» (дубли по регионам).
            if min_rate:
                row_obj.min_rate = min(row_obj.min_rate, min_rate) if row_obj.min_rate else min_rate
            if max_rate:
                row_obj.max_rate = max(row_obj.max_rate, max_rate) if row_obj.max_rate else max_rate
            updated += 1
        else:
            db.add(TariffGrid(position=pos, citizenship=group, min_rate=min_rate, max_rate=max_rate))
            db.flush()  # чтобы следующие строки не дублировали (UNIQUE)
            added += 1

    emit_event(
        db,
        organization_id=org_id,
        actor_user_id=actor_id,
        entity_type="import",
        entity_id=None,
        action="import_tariff_grid",
        payload={"added": added, "updated": updated, "file": path.name},
    )
    db.commit()
    return ImportResult(source=path.name, added=added, updated=updated, skipped=skipped, errors=errors[:50])


def import_daily_assignees(
    db: Session, path: Path, org: Organization, period: EvaluationPeriod, actor_id: int | None = None
) -> ImportResult:
    """Упрощённый ежедневный импорт: Табельный / ФИО / Должность / Участок / Прораб.

    Сотрудник ищется по табельному номеру (нормализованному), его ФИО/должность
    обновляются, закрепление (Assignment) на открытый период создаётся или обновляется
    (evaluate=True, primary_user = прораб/мастер по ФИО).
    """
    _check_zip_bomb(path)
    source = path.name
    added = updated = skipped = 0
    errors: list[str] = []
    try:
        df = pd.read_excel(path, engine="openpyxl", header=0)
    except Exception as exc:  # noqa: BLE001
        return ImportResult(source=source, added=0, updated=0, skipped=0, errors=[f"Не удалось прочитать файл: {exc}"])
    if df is None or df.empty:
        return ImportResult(source=source, added=0, updated=0, skipped=0, errors=["Файл без данных"])

    norm_cols = {nf(str(c)): c for c in df.columns}

    def _find_col(*names: str):
        for name in names:
            key = nf(name)
            for norm_name, col in norm_cols.items():
                if key in norm_name:
                    return col
        return None

    c_tab = _find_col("табель", "таб")
    c_fio = _find_col("фио", "ф.и.о", "фамилия")
    c_pos = _find_col("должн", "професс", "специальн")
    c_site = _find_col("участок", "объект")
    c_pro = _find_col("прораб", "мастер", "оценщик")
    if c_tab is None:
        return ImportResult(
            source=source, added=0, updated=0, skipped=0,
            errors=["Не найдена колонка «Табельный номер» в первой строке файла"],
        )

    def _cell(row, col) -> str:
        if col is None:
            return ""
        v = row[col]
        if v is None:
            return ""
        return str(v).strip()

    # Кэш оценщиков (прораб/мастер) по нормализованному ФИО — без N+1.
    masters = (
        db.query(User)
        .filter(
            User.organization_id == org.id,
            User.status == UserStatus.active,
            User.role.in_([UserRole.master, UserRole.foreman]),
        )
        .all()
    )
    master_by_fio: dict[str, User] = {}
    for m in masters:
        master_by_fio.setdefault(nf(m.fio), m)

    for r_i, row in df.iterrows():
        excel_row = int(r_i) + 2  # заголовок = 1, данные с 2
        tab_no = _norm_tab(_cell(row, c_tab))
        if not tab_no or tab_no.lower() in ("кандидат",):
            skipped += 1
            continue

        emp = (
            db.query(Employee)
            .filter(Employee.organization_id == org.id, Employee.tab_no == tab_no)
            .first()
        )
        if not emp:
            errors.append(f"Строка {excel_row}: сотрудник с табельным {tab_no!r} не найден в базе")
            skipped += 1
            continue

        fio = _cell(row, c_fio)
        position = _cell(row, c_pos)
        site = _cell(row, c_site)
        pro_raw = _cell(row, c_pro)

        emp_changed = False
        if fio and nf(fio) != nf(emp.fio):
            emp.fio = fio
            emp_changed = True
        if position and nf(position) != nf(emp.position_1c or ""):
            emp.position_1c = position
            emp_changed = True

        primary_user = master_by_fio.get(nf(pro_raw)) if pro_raw else None
        if pro_raw and primary_user is None:
            errors.append(f"Строка {excel_row}: оценщик {pro_raw!r} не найден среди активных мастеров/прорабов")

        asg = (
            db.query(Assignment)
            .filter(Assignment.period_id == period.id, Assignment.employee_id == emp.id)
            .first()
        )
        if asg:
            changed = False
            if site and nf(site) != nf(asg.site_name or ""):
                asg.site_name = site
                changed = True
            if primary_user and asg.primary_user_id != primary_user.id:
                asg.primary_user_id = primary_user.id
                changed = True
            if not asg.evaluate:
                asg.evaluate = True
                changed = True
            asg.version = (asg.version or 0) + 1
            updated += 1
        else:
            asg = Assignment(
                organization_id=org.id,
                period_id=period.id,
                employee_id=emp.id,
                site_name=site or emp.territory,
                position_fact=position or emp.position_1c,
                evaluate=True,
                primary_user_id=primary_user.id if primary_user else None,
                dual_enabled=False,
                version=1,
            )
            db.add(asg)
            db.flush()
            added += 1

    emit_event(
        db,
        organization_id=org.id,
        actor_user_id=actor_id,
        entity_type="import",
        entity_id=None,
        action="import_daily_assignees",
        payload={"added": added, "updated": updated, "skipped": skipped, "file": source},
    )
    db.commit()
    return ImportResult(source=source, added=added, updated=updated, skipped=skipped, errors=errors[:50])




# ==================== Новые импорты по формату ТЗ ====================


def _norm_col(row, idx: int) -> str:
    """Безопасное чтение колонки по индексу."""
    if idx >= len(row):
        return ''
    v = row[idx]
    if v is None:
        return ''
    return str(v).strip()


def import_base_v2(db: Session, path: Path, org: Organization, actor_id: int | None = None) -> ImportResult:
    """Импорт 1С по новому формату ТЗ:
    
    A=Табельный, B=ФИО, E=Организация, F=Подразделение, G=Должность,
    H=Разряд, I=Состояние, K=Дата приема, L=Дата увольнения,
    M=Страна гражданства, N=Территория
    """
    _check_zip_bomb(path)
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    added = updated = archived = skipped = 0
    errors: list[str] = []
    today = date.today()
    # Открытые периоды организации: уволенные снимаются с оценивания только в них.
    open_period_ids = [
        p.id
        for p in db.query(EvaluationPeriod)
        .filter(EvaluationPeriod.organization_id == org.id, EvaluationPeriod.is_open.is_(True))
        .all()
    ]
    
    for i, row in enumerate(ws.iter_rows(values_only=True), 1):
        if i == 1:
            continue  # заголовок
        if not row or not row[0]:
            continue
        
        tab_no = _norm_col(row, 0)  # A
        fio = _norm_col(row, 1)      # B
        # C, D - Удостоверение НЕ НУЖНЫ
        # E - Организация (row[4])
        dept = _norm_col(row, 5)     # F
        position = _norm_col(row, 6) # G
        category = _norm_col(row, 7) # H
        state = _norm_col(row, 8)    # I
        # J - График работы НЕ НУЖЕН
        hire_date = parse_date(row[10]) if len(row) > 10 else None  # K
        fire_date = parse_date(row[11]) if len(row) > 11 else None  # L
        citizenship = _norm_col(row, 12) if len(row) > 12 else None  # M
        territory = _norm_col(row, 13) if len(row) > 13 else None    # N
        # O-X НЕ НУЖНЫ
        
        if not fio:
            skipped += 1
            continue
        
        # Если есть дата увольнения -- архивируем
        if fire_date:
            existing = (
                db.query(Employee)
                .filter(Employee.organization_id == org.id, Employee.tab_no == tab_no)
                .first()
            )
            if existing:
                # Идемпотентный архив: upsert по (организация, табельный) —
                # повторный импорт обновляет запись, а не создаёт дубль.
                fe = (
                    db.query(FiredEmployee)
                    .filter(
                        FiredEmployee.organization_id == org.id,
                        FiredEmployee.tab_no == existing.tab_no,
                    )
                    .first()
                )
                archive_fields = {
                    "original_employee_id": existing.id,
                    "fio": existing.fio,
                    "territory": existing.territory,
                    "department_1c": existing.department_1c,
                    "position_1c": existing.position_1c,
                    "category": existing.category,
                    "citizenship": existing.citizenship,
                    "hire_date": existing.hire_date,
                    "fire_date": fire_date,
                    "state": existing.state,
                    "hourly_rate": existing.hourly_rate,
                    "fired_by_user_id": actor_id,
                }
                if fe:
                    for k, v in archive_fields.items():
                        setattr(fe, k, v)
                else:
                    db.add(FiredEmployee(organization_id=org.id, tab_no=existing.tab_no, **archive_fields))
                existing.state = "Уволен"
                # Уволенный не участвует в оценивании: снимаем evaluate
                # с назначений открытых периодов (сами назначения и оценки сохраняются).
                if open_period_ids:
                    db.query(Assignment).filter(
                        Assignment.employee_id == existing.id,
                        Assignment.period_id.in_(open_period_ids),
                        Assignment.evaluate.is_(True),
                    ).update({Assignment.evaluate: False}, synchronize_session=False)
                archived += 1
            continue
        
        # Испытательный срок: если от даты приема прошло менее 3 месяцев
        probation_end = None
        if hire_date:
            probation_end = hire_date + timedelta(days=90)
        
        emp = (
            db.query(Employee)
            .filter(Employee.organization_id == org.id, Employee.tab_no == tab_no)
            .first()
        )
        
        fields = {
            "fio": fio,
            "territory": territory or None,
            "department_1c": dept or None,
            "position_1c": position or None,
            "category": category or None,
            "state": state or None,
            "hire_date": hire_date,
            "citizenship": citizenship or None,
            "probation_end_date": probation_end,
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
        except Exception as exc:
            errors.append(f"R{i} {tab_no}: {exc}")
            skipped += 1
    
    wb.close()
    db.commit()
    return ImportResult(source=path.name, added=added, updated=updated, skipped=skipped + archived, errors=errors[:50])


def import_daily_v2(db: Session, path: Path, org: Organization, period, actor_id: int | None = None) -> ImportResult:
    """Импорт Ежедневный учет по новому формату:
    
    Лист "ЕЖЕДНЕВНЫЙ УЧЕТ", заголовки на строке 5, данные с строки 6.
    C=Площадка, D=Табельный, E=ФИО, G=Гражданство,
    J=Фактическая должность, K=Участок/Отдел, P=Дата прилета
    """
    _check_zip_bomb(path)
    added = updated = skipped = 0
    errors: list[str] = []
    today = date.today()
    
    wb = load_workbook(path, read_only=True, data_only=True)
    target_sheet = None
    for name in wb.sheetnames:
        if "ежедневн" in name.lower():
            target_sheet = wb[name]
            break
    if not target_sheet:
        target_sheet = wb.active
    
    # Данные с строки 6 (заголовок на строке 5)
    for i, row in enumerate(target_sheet.iter_rows(values_only=True), 1):
        if i < 6:
            continue  # пропускаем строки 1-5
        
        excel_row = i
        territory = _norm_col(row, 2)   # C
        tab_no = _norm_col(row, 3)      # D
        fio = _norm_col(row, 4)         # E
        # F - Дата рождения НЕ НУЖЕН
        citizenship = _norm_col(row, 6) # G
        # H, I - Серия, Паспорт НЕ НУЖНЫ
        position = _norm_col(row, 9)    # J
        site = _norm_col(row, 10)       # K
        # L-P - Виза, Вид визы, Регион, Срок до НЕ НУЖНЫ
        date_arrival = parse_date(row[15]) if len(row) > 15 else None  # P
        
        # Проверяем, кандидат ли
        is_candidate = False
        if tab_no:
            tab_upper = tab_no.upper().strip()
            if tab_upper in ("КАНДИДАТ", "НЕЛЕГАЛ", "ПРИЕМ"):
                is_candidate = True
                storage_tab = f"КАНД-{nf(fio)[:40]}" if fio else f"КАНД-R{excel_row}"
                tab_no = storage_tab
        
        if not tab_no and not fio:
            skipped += 1
            continue
        
        emp = (
            db.query(Employee)
            .filter(Employee.organization_id == org.id, Employee.tab_no == tab_no)
            .first()
        )
        
        fields = {
            "fio": fio or None,
            "territory": territory or None,
            "citizenship": citizenship or None,
            "position_1c": position or None,
            "is_candidate": is_candidate,
        }
        
        # Испытательный срок: если есть дата прилета и прошло < 3 месяцев
        if date_arrival and not is_candidate:
            probation_end = date_arrival + timedelta(days=90)
            fields["probation_end_date"] = probation_end
            fields["hire_date"] = date_arrival
        
        try:
            if emp:
                for k, v in fields.items():
                    setattr(emp, k, v)
                updated += 1
            else:
                db.add(Employee(organization_id=org.id, tab_no=tab_no, **fields))
                added += 1
        except Exception as exc:
            errors.append(f"Строка {excel_row}: {exc}")
            skipped += 1
    
    wb.close()
    db.commit()
    return ImportResult(source=path.name, added=added, updated=updated, skipped=skipped, errors=errors[:50])


def import_users_v2(db: Session, path: Path, org: Organization, actor_id: int | None = None) -> ImportResult:
    """Импорт пользователей из файла с тремя листами:
    
    1. Group_of_Users: Territory, Role, Group_of_Users, Permission
    2. Users: Group_of_Users, Users, Actual_position
    3. Прораб_Мастер: Group_of_Users, Табельный номер, User, Подразделение, Actual_position, Территория
    """
    _check_zip_bomb(path)
    added = updated = skipped = 0
    errors: list[str] = []
    
    wb = load_workbook(path, read_only=True, data_only=True)
    
    # --- Лист 1: Group_of_Users ---
    if "Group_of_Users" in wb.sheetnames:
        ws = wb["Group_of_Users"]
        for i, row in enumerate(ws.iter_rows(values_only=True), 1):
            if i == 1:
                continue
            territory_name = _norm_col(row, 0)
            role_name = _norm_col(row, 1)
            group_name = _norm_col(row, 2)
            permission = _norm_col(row, 3) if len(row) > 3 else None
            
            if not territory_name or not role_name:
                continue
            
            # Создаем Territory и Department если нет
            territory = (
                db.query(Territory)
                .filter(Territory.organization_id == org.id, Territory.name == territory_name)
                .first()
            )
            if not territory:
                territory = Territory(organization_id=org.id, name=territory_name)
                db.add(territory)
                db.flush()
            
            dept_code = map_role(role_name)
            if not dept_code:
                for name, code in CONTROL_ROLES:
                    if role_name in name:
                        dept_code = code
                        break
            
            department = None
            if dept_code:
                department = (
                    db.query(Department)
                    .filter(Department.organization_id == org.id, Department.name == role_name)
                    .first()
                )
                if not department:
                    department = Department(
                        organization_id=org.id,
                        name=role_name,
                        code=dept_code.value if hasattr(dept_code, 'value') else str(dept_code),
                        system_role=dept_code.value if hasattr(dept_code, 'value') else str(dept_code),
                    )
                    db.add(department)
                    db.flush()
            
            # Сохраняем GroupOfUsers
            from app.models import GroupOfUsers as GOU
            existing = (
                db.query(GOU)
                .filter(
                    GOU.organization_id == org.id,
                    GOU.territory_name == territory_name,
                    GOU.department_name == role_name,
                    GOU.group_name == group_name,
                )
                .first()
            )
            if not existing:
                db.add(GOU(
                    organization_id=org.id,
                    territory_id=territory.id,
                    territory_name=territory_name,
                    department_id=department.id if department else None,
                    department_name=role_name,
                    group_name=group_name,
                    permission=permission,
                ))
                added += 1
    
    # --- Лист 2: Users ---
    if "Users" in wb.sheetnames:
        ws = wb["Users"]
        for i, row in enumerate(ws.iter_rows(values_only=True), 1):
            if i == 1:
                continue
            group_name = _norm_col(row, 0)
            user_fio = _norm_col(row, 1)
            actual_pos = _norm_col(row, 2) if len(row) > 2 else None
            
            if not user_fio:
                continue
            
            user = (
                db.query(User)
                .filter(User.organization_id == org.id, User.fio == user_fio)
                .first()
            )
            if user:
                from app.models import UserTerritoryMapping as UTM
                existing = (
                    db.query(UTM)
                    .filter(UTM.user_id == user.id, UTM.group_name == group_name)
                    .first()
                )
                if not existing:
                    db.add(UTM(
                        user_id=user.id,
                        group_name=group_name,
                        actual_position=actual_pos,
                    ))
                    added += 1
    
    # --- Лист 3: Прораб_Мастер ---
    if "Прораб_Мастер" in wb.sheetnames:
        ws = wb["Прораб_Мастер"]
        for i, row in enumerate(ws.iter_rows(values_only=True), 1):
            if i == 1:
                continue
            group_name = _norm_col(row, 0)
            tab_no = _norm_col(row, 1)
            user_fio = _norm_col(row, 2)
            dept = _norm_col(row, 3) if len(row) > 3 else None
            actual_pos = _norm_col(row, 4) if len(row) > 4 else None
            territory = _norm_col(row, 5) if len(row) > 5 else None
            
            if not tab_no or not user_fio:
                continue
            
            tab_norm = tab_no.strip().upper()
            
            user = (
                db.query(User)
                .filter(User.organization_id == org.id, User.tab_no == tab_norm)
                .first()
            )
            if not user:
                temp_pwd = generate_temporary_password()
                user = User(
                    organization_id=org.id,
                    tab_no=tab_norm,
                    fio=user_fio,
                    role=UserRole.master,
                    status=UserStatus.active,
                    password_hash=hash_password(temp_pwd),
                    must_change_password=True,
                )
                db.add(user)
                db.flush()
                added += 1
            
            from app.models import UserTerritoryMapping as UTM
            existing = (
                db.query(UTM)
                .filter(UTM.user_id == user.id)
                .first()
            )
            if existing:
                existing.actual_position = actual_pos or existing.actual_position
                updated += 1
    
    wb.close()
    db.commit()
    return ImportResult(source=path.name, added=added, updated=updated, skipped=skipped, errors=errors[:50])


# ==================== Константы для слайдов ====================
CONTROL_ROLES = [
    ("Линейный ИТР", "master"),
    ("Линейный ИТР2", "foreman"),
    ("Администрация ОП", "admin_op"),
    ("Экономисты ОП", "economist"),
    ("Руководство ОП", "management_op"),
    ("ЦОК_ОКиТ", "cok_okit"),
    ("ЦОК_Адаптация", "cok_adapt"),
    ("ЦОК_ОТиЗ", "cok_otiz"),
]



# ==================== Импорт реестров оценок (12 критериев) ====================


def import_registry_scores(db: Session, path: Path, org: Organization,
                           year: int, half: int, slot_name: str,
                           actor_id: int | None = None) -> ImportResult:
    """Импорт реестров оценок по формату ТЗ:
    
    A=No, B=ТАБ№, C=ФИО, D=ПЛОЩАДКА, E=ДОЛЖНОСТЬ, F=ПОДРАЗДЕЛЕНИЕ,
    G=ФИО мастера, H-S=12 критериев 1-й оценки, T=Средняя 1,
    U=ФИО ПР, V-AG=12 критериев 2-й оценки, AH=Средняя 2,
    AI=Коэфф выработки, AJ=Итоговая
    
    H-S критерии:
    1. Фиксация терминалом
    2. Трудовая дисциплина
    3. Взаимодействие внутри коллектива
    4. Охрана труда
    5. Отношение к руководству
    6. Качество выполнения работы
    7. Способность менять рабочее место
    8. Знание технологии
    9. Знание материалов
    10. Ответственность
    11. Выполнение сложных работ
    12. Прогресс в новых навыках
    """
    _check_zip_bomb(path)
    added = updated = skipped = 0
    errors: list[str] = []
    
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    
    # Заголовки на строке 1
    header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
    
    # Карта заголовков
    col_map: dict[str, int] = {}
    for idx, h in enumerate(header_row):
        if h is not None:
            col_map[str(h).strip().upper()] = idx
    
    def get_col(*names: str):
        for n in names:
            if n in col_map:
                return col_map[n]
        return None
    
    c_tab = get_col("ТАБ№", "ТАБЕЛЬНЫЙ НОМЕР")
    c_fio = get_col("ФИО")
    c_territory = get_col("ПЛОЩАДКА")
    c_position = get_col("ДОЛЖНОСТЬ")
    c_department = get_col("ПОДРАЗДЕЛЕНИЕ", "ОТДЕЛ")
    c_master = get_col("ФИО МАСТЕРА")
    c_prod = get_col("ФИО ПРОИЗВОДИТЕЛЯ РАБОТ")
    
    if c_tab is None:
        wb.close()
        return ImportResult(source=path.name, added=0, updated=0, skipped=0,
                          errors=["Не найдена колонка Табельный номер"])
    
    # Индексы критериев 1-й оценки: H=7, I=8, ..., S=18
    first_criteria_cols = list(range(7, 19))  # H-S
    # Индексы критериев 2-й оценки: V=21, W=22, ..., AG=32
    second_criteria_cols = list(range(21, 33))  # V-AG
    
    c_avg_first = get_col("СРЕДНЯЯ ОЦЕНКА 1", "СРЕДНЯЯ ОЦЕНКА1")
    c_avg_second = get_col("СРЕДНЯЯ ОЦЕНКА 2", "СРЕДНЯЯ ОЦЕНКА2")
    c_prod_coeff = get_col("КОЭФФИЦИЕНТ", "ПРОИЗВОДСТВЕННОЙ ВЫРАБОТКИ")
    c_final = get_col("ИТОГОВАЯ ОЦЕНКА")
    
    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
        if not row or (c_tab is not None and not row[c_tab]):
            continue
        
        tab_no = _norm_col(row, c_tab) if c_tab is not None else ""
        fio = _norm_col(row, c_fio) if c_fio is not None else ""
        territory = _norm_col(row, c_territory) if c_territory is not None else ""
        position = _norm_col(row, c_position) if c_position is not None else ""
        department = _norm_col(row, c_department) if c_department is not None else ""
        master_fio = _norm_col(row, c_master) if c_master is not None else ""
        prod_fio = _norm_col(row, c_prod) if c_prod is not None else ""
        
        if not tab_no:
            skipped += 1
            continue
        
        # Читаем 12 критериев первой оценки
        first_scores: list[int | None] = []
        for col_idx in first_criteria_cols:
            if col_idx < len(row):
                v = row[col_idx]
                try:
                    first_scores.append(int(float(v)) if v not in (None, "") else None)
                except (ValueError, TypeError):
                    first_scores.append(None)
            else:
                first_scores.append(None)
        
        # Читаем 12 критериев второй оценки
        second_scores: list[int | None] = []
        for col_idx in second_criteria_cols:
            if col_idx < len(row):
                v = row[col_idx]
                try:
                    second_scores.append(int(float(v)) if v not in (None, "") else None)
                except (ValueError, TypeError):
                    second_scores.append(None)
            else:
                second_scores.append(None)
        
        # Средние
        avg_first = None
        valid_first = [s for s in first_scores if s is not None]
        if valid_first:
            avg_first = round(sum(valid_first) / len(valid_first), 2)
        
        avg_second = None
        valid_second = [s for s in second_scores if s is not None]
        if valid_second:
            avg_second = round(sum(valid_second) / len(valid_second), 2)
        
        # Коэффициент и итоговая
        prod_coeff = None
        if c_prod_coeff is not None and c_prod_coeff < len(row):
            prod_coeff = _to_float(row[c_prod_coeff])
        
        final_score = None
        if c_final is not None and c_final < len(row):
            final_score = _to_float(row[c_final])
        
        # Создаём или обновляем RegistryScore
        from app.models import RegistryImport, RegistryScore
        
        # Находим или создаём RegistryImport
        ri = (
            db.query(RegistryImport)
            .filter(
                RegistryImport.organization_id == org.id,
                RegistryImport.period_year == year,
                RegistryImport.period_half == half,
            )
            .first()
        )
        if not ri:
            ri = RegistryImport(
                organization_id=org.id,
                period_year=year,
                period_half=half,
                file_name=path.name,
                uploaded_by_user_id=actor_id,
            )
            db.add(ri)
            db.flush()
        
        # Находим существующую запись
        existing = (
            db.query(RegistryScore)
            .filter(
                RegistryScore.organization_id == org.id,
                RegistryScore.registry_import_id == ri.id,
                RegistryScore.tab_no == tab_no,
            )
            .first()
        )
        
        score_data = {
            "registry_import_id": ri.id,
            "tab_no": tab_no,
            "fio": fio,
            "territory": territory or None,
            "position": position or None,
            "department": department or None,
            "master_fio": master_fio or None,
            "c1_first": first_scores[0],
            "c2_first": first_scores[1],
            "c3_first": first_scores[2],
            "c4_first": first_scores[3],
            "c5_first": first_scores[4],
            "c6_first": first_scores[5],
            "c7_first": first_scores[6],
            "c8_first": first_scores[7],
            "c9_first": first_scores[8],
            "c10_first": first_scores[9],
            "c11_first": first_scores[10],
            "c12_first": first_scores[11],
            "avg_first": avg_first,
            "c1_second": second_scores[0],
            "c2_second": second_scores[1],
            "c3_second": second_scores[2],
            "c4_second": second_scores[3],
            "c5_second": second_scores[4],
            "c6_second": second_scores[5],
            "c7_second": second_scores[6],
            "c8_second": second_scores[7],
            "c9_second": second_scores[8],
            "c10_second": second_scores[9],
            "c11_second": second_scores[10],
            "c12_second": second_scores[11],
            "avg_second": avg_second,
            "prod_coeff": prod_coeff,
            "final_score": final_score,
        }
        
        try:
            if existing:
                for k, v in score_data.items():
                    setattr(existing, k, v)
                updated += 1
            else:
                db.add(RegistryScore(organization_id=org.id, **score_data))
                added += 1
        except Exception as exc:
            errors.append(f"R{i} {tab_no}: {exc}")
            skipped += 1
    
    wb.close()
    db.commit()
    
    return ImportResult(
        source=path.name,
        added=added,
        updated=updated,
        skipped=skipped,
        errors=errors[:50],
    )
