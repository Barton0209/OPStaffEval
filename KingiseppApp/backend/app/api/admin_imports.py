"""API для управления импортами, журналами и архивом уволенных."""

import tempfile
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import require_roles
from app.models import (
    Employee,
    FiredEmployee,
    ImportLog,
    Organization,
    User,
    UserRole,
)
from app.schemas import ImportResult
from app.services.imports import (
    ensure_org_by_id,
    import_base_v2,
    import_daily_v2,
    import_registry_scores,
    import_users_v2,
    nf,
)

router = APIRouter(prefix="/api/admin", tags=["admin_imports"])
settings = get_settings()

ALLOWED_BLOCKS = {
    "База сотрудников": {"folder": "01_Base", "func": import_base_v2, "role": UserRole.admin_op},
    "Ежедневный учет": {"folder": "02_Daily_report", "func": import_daily_v2, "role": UserRole.admin_op},
    "Пользователи, роли, доступ": {"folder": "03_Users_Role_Permision", "func": import_users_v2, "role": UserRole.admin_op},
}

REGISTRY_SLOTS = [
    ("2024 1 полугодие", 2024, 1),
    ("2024 2 полугодие", 2024, 2),
    ("2025 1 полугодие", 2025, 1),
    ("2025 2 полугодие", 2025, 2),
    ("2026 1 полугодие", 2026, 1),
    ("2026 2 полугодие", 2026, 2),
]


def _upload_dir(block: str, slot: str | None = None) -> Path:
    """Каталог для загрузки файлов."""
    base = Path(settings.files_dir) / "UpLoad"
    if block == "Реестры оценок" and slot:
        return base / "05_Old_rating_register"
    folder = ALLOWED_BLOCKS.get(block, {}).get("folder", "01_Base")
    return base / folder


@router.post("/import/upload")
def upload_import_file(
    block: str,
    file: UploadFile,
    slot: str | None = None,
    user: User = Depends(require_roles(UserRole.admin_op, UserRole.admin, UserRole.cok_okit)),
    db: Session = Depends(get_db),
):
    """Загрузить и импортировать Excel-файл."""
    org, _period = ensure_org_by_id(db, user.organization_id)

    if block != "Реестры оценок" and block not in ALLOWED_BLOCKS:
        raise HTTPException(status_code=400, detail="Неизвестный блок импорта")
    safe_name = Path(file.filename or "").name
    if not safe_name or Path(safe_name).suffix.lower() not in {".xlsx", ".xlsb"}:
        raise HTTPException(status_code=400, detail="Разрешены только .xlsx и .xlsb")

    # Проверяем право доступа
    allowed_block = ALLOWED_BLOCKS.get(block)
    if allowed_block and user.role != allowed_block["role"] and user.role != UserRole.admin and user.role != UserRole.cok_okit:
        raise HTTPException(status_code=403, detail="Нет права на этот импорт")
    
    # Для реестров — проверяем slot
    if block == "Реестры оценок":
        found = False
        for name, year, half in REGISTRY_SLOTS:
            if name == slot:
                found = True
                break
        if not found:
            raise HTTPException(status_code=400, detail=f"Недопустимый слот: {slot}")
    
    # Validate before invoking a parser; never retain an untrusted upload.
    upload_path = _upload_dir(block, slot)
    upload_path.mkdir(parents=True, exist_ok=True)
    max_bytes = settings.max_upload_mb * 1024 * 1024
    total = 0
    with tempfile.NamedTemporaryFile(dir=upload_path, suffix=Path(safe_name).suffix, delete=False) as tmp:
        dest_path = Path(tmp.name)
        while chunk := file.file.read(1024 * 1024):
            total += len(chunk)
            if total > max_bytes:
                dest_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Файл превышает допустимый размер")
            tmp.write(chunk)
    if dest_path.read_bytes()[:4] != b"PK\x03\x04":
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Некорректная сигнатура Excel")

    try:
        if block == "Реестры оценок" and slot:
            # Определяем year/half из slot
            year_half = None
            for name, year, half in REGISTRY_SLOTS:
                if name == slot:
                    year_half = (year, half)
                    break
            if year_half:
                result = import_registry_scores(db, dest_path, org, year_half[0], year_half[1], slot, actor_id=user.id)
            else:
                raise HTTPException(status_code=400, detail="Не удалось определить период из слота")
        elif block == "База сотрудников":
            result = import_base_v2(db, dest_path, org, actor_id=user.id)
        elif block == "Ежедневный учет":
            _, period = ensure_org_by_id(db, user.organization_id)
            result = import_daily_v2(db, dest_path, org, period, actor_id=user.id)
        elif block == "Пользователи, роли, доступ":
            result = import_users_v2(db, dest_path, org, actor_id=user.id)
        else:
            raise HTTPException(status_code=400, detail=f"Неизвестный блок: {block}")
        
        # Записываем в журнал
        db.add(ImportLog(
            organization_id=org.id,
            block_name=block,
            slot_name=slot,
            file_name=safe_name,
            uploaded_by_user_id=user.id,
            added=result.added,
            updated=result.updated,
            skipped=result.skipped,
            errors_count=len(result.errors),
            error_preview="; ".join(result.errors[:3]) if result.errors else None,
            success=len(result.errors) == 0,
        ))
        db.commit()
        
        return {
            "ok": True,
            "result": {
                "added": result.added,
                "updated": result.updated,
                "skipped": result.skipped,
                "errors": result.errors[:10],
            },
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Файл не удалось проверить или импортировать") from None
    finally:
        dest_path.unlink(missing_ok=True)


@router.get("/import-log")
def get_import_log(
    block: str | None = None,
    user: User = Depends(require_roles(UserRole.admin_op, UserRole.admin, UserRole.cok_okit)),
    db: Session = Depends(get_db),
):
    """Журнал импортов."""
    org, _ = ensure_org_by_id(db, user.organization_id)
    
    query = db.query(ImportLog).filter(
        ImportLog.organization_id == org.id,
    )
    if block:
        query = query.filter(ImportLog.block_name == block)
    
    logs = query.order_by(ImportLog.uploaded_at.desc()).limit(100).all()
    
    return [
        {
            "id": log.id,
            "block_name": log.block_name,
            "slot_name": log.slot_name,
            "file_name": log.file_name,
            "uploaded_at": log.uploaded_at.strftime("%d.%m.%Y %H:%M") if log.uploaded_at else None,
            "added": log.added,
            "updated": log.updated,
            "skipped": log.skipped,
            "errors_count": log.errors_count,
            "error_preview": log.error_preview,
            "success": log.success,
        }
        for log in logs
    ]


@router.get("/import-log/latest")
def get_latest_import(
    block: str,
    user: User = Depends(require_roles(UserRole.admin_op, UserRole.admin, UserRole.cok_okit)),
    db: Session = Depends(get_db),
):
    """Последняя загрузка для блока."""
    org, _ = ensure_org_by_id(db, user.organization_id)
    
    log = (
        db.query(ImportLog)
        .filter(
            ImportLog.organization_id == org.id,
            ImportLog.block_name == block,
        )
        .order_by(ImportLog.uploaded_at.desc())
        .first()
    )
    
    if not log:
        return {"found": False}
    
    return {
        "found": True,
        "file_name": log.file_name,
        "uploaded_at": log.uploaded_at.strftime("%d.%m.%Y %H:%M") if log.uploaded_at else None,
        "added": log.added,
        "updated": log.updated,
        "success": log.success,
    }


# ==================== Архив уволенных ====================


@router.get("/fired")
def list_fired_employees(
    search: str | None = None,
    user: User = Depends(require_roles(UserRole.admin_op, UserRole.admin, UserRole.cok_okit)),
    db: Session = Depends(get_db),
):
    """Список уволенных сотрудников."""
    org, _ = ensure_org_by_id(db, user.organization_id)
    
    query = db.query(FiredEmployee).filter(
        FiredEmployee.organization_id == org.id,
    )
    if search:
        query = query.filter(
            FiredEmployee.fio.ilike(f"%{search}%") | FiredEmployee.tab_no.ilike(f"%{search}%")
        )
    
    employees = query.order_by(FiredEmployee.fired_at.desc()).limit(200).all()
    
    return [
        {
            "id": fe.id,
            "tab_no": fe.tab_no,
            "fio": fe.fio,
            "position_1c": fe.position_1c,
            "department_1c": fe.department_1c,
            "hire_date": fe.hire_date.isoformat() if fe.hire_date else None,
            "fire_date": fe.fire_date.isoformat() if fe.fire_date else None,
            "state": fe.state,
            "fired_at": fe.fired_at.strftime("%d.%m.%Y %H:%M") if fe.fired_at else None,
        }
        for fe in employees
    ]


@router.get("/fired/export.xlsx")
def export_fired_employees(
    user: User = Depends(require_roles(UserRole.admin_op, UserRole.admin, UserRole.cok_okit)),
    db: Session = Depends(get_db),
):
    """Выгрузка архива уволенных в Excel."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment
    
    org, _ = ensure_org_by_id(db, user.organization_id)
    
    employees = (
        db.query(FiredEmployee)
        .filter(FiredEmployee.organization_id == org.id)
        .order_by(FiredEmployee.fired_at.desc())
        .all()
    )
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Уволенные"
    
    # Заголовки
    headers = ["Табельный", "ФИО", "Должность", "Подразделение", "Разряд", 
               "Гражданство", "Дата приёма", "Дата увольнения", "Статус", "Дата увольнения (система)"]
    ws.append(headers)
    
    for fe in employees:
        ws.append([
            fe.tab_no,
            fe.fio,
            fe.position_1c or "",
            fe.department_1c or "",
            fe.category or "",
            fe.citizenship or "",
            fe.hire_date.isoformat() if fe.hire_date else "",
            fe.fire_date.isoformat() if fe.fire_date else "",
            fe.state or "",
            fe.fired_at.strftime("%d.%m.%Y %H:%M") if fe.fired_at else "",
        ])
    
    # Сохраняем во временный файл
    fd, path = tempfile.mkstemp(suffix=".xlsx", prefix="fired_")
    import os
    os.close(fd)
    wb.save(path)
    
    return FileResponse(
        path,
        filename=f"Уволенные_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
