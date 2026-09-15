"""API CRUD для Group_of_Users: Territory → Role → Group → Permission + фото."""

import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import (
    Department,
    GroupOfUsers,
    Organization,
    Territory,
    User,
    UserTerritoryMapping,
)
from app.schemas import GroupOfUsersCreate, GroupOfUsersUpdate

settings = get_settings()
router = APIRouter(prefix="/api/groups", tags=["groups_of_users"])


def _get_photo_dir() -> Path:
    """Возвращает директорию с фото из @Files/UpLoad/Foto."""
    # Пытаемся найти директорию Foto в Files/UpLoad/
    photo_dir = settings.files_path / "UpLoad" / "Foto"
    if not photo_dir.exists():
        # Fallback: ищем в data_dir
        photo_dir = settings.data_dir.parent / "Files" / "UpLoad" / "Foto"
    return photo_dir

router = APIRouter(prefix="/api/groups", tags=["groups_of_users"])


def _get_default_org(db: Session) -> Organization:
    org = db.query(Organization).first()
    if not org:
        org = Organization(code="kingisepp", name="Кингисепп (ВСМ)")
        db.add(org)
        db.flush()
    return org


# ==================== Площадки ====================

@router.get("/territories")
def list_territories(db: Session = Depends(get_db)):
    """Список всех площадок."""
    org = _get_default_org(db)
    territories = (
        db.query(Territory)
        .filter(Territory.organization_id == org.id)
        .order_by(Territory.name)
        .all()
    )
    return [{"id": t.id, "code": t.code, "name": t.name} for t in territories]


# ==================== Отделы ====================

@router.get("/departments")
def list_departments(
    territory: str | None = Query(None, description="Фильтр по площадке"),
    db: Session = Depends(get_db),
):
    """Список отделов, опционально отфильтрованный по площадке."""
    org = _get_default_org(db)
    
    if territory:
        groups = (
            db.query(GroupOfUsers)
            .filter(
                GroupOfUsers.organization_id == org.id,
                GroupOfUsers.territory_name == territory,
            )
            .all()
        )
        if groups:
            seen = set()
            result = []
            for g in groups:
                if g.department_name and g.department_name not in seen:
                    seen.add(g.department_name)
                    result.append({
                        "id": g.department_id,
                        "name": g.department_name,
                    })
            if result:
                return result
    
    # Fallback: все отделы
    departments = (
        db.query(Department)
        .filter(Department.organization_id == org.id)
        .order_by(Department.name)
        .all()
    )
    return [{"id": d.id, "name": d.name} for d in departments]


# ==================== Группы пользователей ====================

@router.get("")
def list_groups(
    territory: str | None = Query(None, description="Фильтр по площадке"),
    department: str | None = Query(None, description="Фильтр по отделу"),
    db: Session = Depends(get_db),
):
    """Список групп пользователей."""
    org = _get_default_org(db)
    
    query = db.query(GroupOfUsers).filter(
        GroupOfUsers.organization_id == org.id,
    )
    
    if territory:
        query = query.filter(GroupOfUsers.territory_name == territory)
    if department:
        query = query.filter(GroupOfUsers.department_name == department)
    
    groups = query.order_by(GroupOfUsers.territory_name, GroupOfUsers.department_name, GroupOfUsers.group_name).all()
    
    return [
        {
            "id": g.id,
            "territory_id": g.territory_id,
            "territory_name": g.territory_name,
            "department_id": g.department_id,
            "department_name": g.department_name,
            "group_name": g.group_name,
            "permission": g.permission,
        }
        for g in groups
    ]


@router.post("")
def create_group(
    payload: GroupOfUsersCreate,
    db: Session = Depends(get_db),
):
    """Создать группу пользователей."""
    org = _get_default_org(db)
    
    # Создаём Territory если нет
    territory = (
        db.query(Territory)
        .filter(
            Territory.organization_id == org.id,
            Territory.name == payload.territory_name,
        )
        .first()
    )
    if not territory:
        territory = Territory(
            organization_id=org.id,
            name=payload.territory_name,
            code=payload.territory_name.lower().replace(" ", "_"),
        )
        db.add(territory)
        db.flush()
    
    # Создаём Department если нет
    department = None
    if payload.department_name:
        department = (
            db.query(Department)
            .filter(
                Department.organization_id == org.id,
                Department.name == payload.department_name,
            )
            .first()
        )
        if not department:
            department = Department(
                organization_id=org.id,
                name=payload.department_name,
                code=payload.department_name.lower().replace(" ", "_"),
            )
            db.add(department)
            db.flush()
    
    # Проверяем дубликат
    existing = (
        db.query(GroupOfUsers)
        .filter(
            GroupOfUsers.organization_id == org.id,
            GroupOfUsers.territory_name == payload.territory_name,
            GroupOfUsers.department_name == payload.department_name,
            GroupOfUsers.group_name == payload.group_name,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Группа уже существует")
    
    group = GroupOfUsers(
        organization_id=org.id,
        territory_id=territory.id,
        territory_name=payload.territory_name,
        department_id=department.id if department else None,
        department_name=payload.department_name,
        group_name=payload.group_name,
        permission=payload.permission,
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    
    return {
        "id": group.id,
        "territory_id": group.territory_id,
        "territory_name": group.territory_name,
        "department_id": group.department_id,
        "department_name": group.department_name,
        "group_name": group.group_name,
        "permission": group.permission,
    }


@router.put("/{group_id}")
def update_group(
    group_id: int,
    payload: GroupOfUsersUpdate,
    db: Session = Depends(get_db),
):
    """Обновить группу пользователей."""
    org = _get_default_org(db)
    
    group = (
        db.query(GroupOfUsers)
        .filter(
            GroupOfUsers.id == group_id,
            GroupOfUsers.organization_id == org.id,
        )
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    
    if payload.territory_name is not None:
        territory = (
            db.query(Territory)
            .filter(
                Territory.organization_id == org.id,
                Territory.name == payload.territory_name,
            )
            .first()
        )
        if not territory:
            territory = Territory(
                organization_id=org.id,
                name=payload.territory_name,
                code=payload.territory_name.lower().replace(" ", "_"),
            )
            db.add(territory)
            db.flush()
        group.territory_id = territory.id
        group.territory_name = payload.territory_name
    
    if payload.department_name is not None:
        department = (
            db.query(Department)
            .filter(
                Department.organization_id == org.id,
                Department.name == payload.department_name,
            )
            .first()
        )
        if not department:
            department = Department(
                organization_id=org.id,
                name=payload.department_name,
                code=payload.department_name.lower().replace(" ", "_"),
            )
            db.add(department)
            db.flush()
        group.department_id = department.id
        group.department_name = payload.department_name
    
    if payload.group_name is not None:
        group.group_name = payload.group_name
    if payload.permission is not None:
        group.permission = payload.permission
    
    db.commit()
    db.refresh(group)
    
    return {
        "id": group.id,
        "territory_id": group.territory_id,
        "territory_name": group.territory_name,
        "department_id": group.department_id,
        "department_name": group.department_name,
        "group_name": group.group_name,
        "permission": group.permission,
    }


@router.delete("/{group_id}")
def delete_group(
    group_id: int,
    db: Session = Depends(get_db),
):
    """Удалить группу пользователей."""
    org = _get_default_org(db)
    
    group = (
        db.query(GroupOfUsers)
        .filter(
            GroupOfUsers.id == group_id,
            GroupOfUsers.organization_id == org.id,
        )
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    
    db.delete(group)
    db.commit()
    
    return {"detail": "Группа удалена"}


# ==================== Пользователи в группе ====================

@router.get("/{group_id}/users")
def list_group_users(
    group_id: int,
    db: Session = Depends(get_db),
):
    """Список пользователей в группе."""
    org = _get_default_org(db)
    
    group = (
        db.query(GroupOfUsers)
        .filter(
            GroupOfUsers.id == group_id,
            GroupOfUsers.organization_id == org.id,
        )
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    
    mappings = (
        db.query(UserTerritoryMapping)
        .filter(UserTerritoryMapping.group_name == group.group_name)
        .all()
    )
    
    user_ids = [m.user_id for m in mappings]
    if not user_ids:
        return []
    
    users = (
        db.query(User)
        .filter(User.id.in_(user_ids))
        .order_by(User.fio)
        .all()
    )
    
    return [
        {
            "id": u.id,
            "tab_no": u.tab_no,
            "fio": u.fio,
            "role": u.role.value,
            "status": u.status.value if hasattr(u.status, 'value') else u.status,
        }
        for u in users
    ]


@router.post("/{group_id}/users/{user_id}")
def add_user_to_group(
    group_id: int,
    user_id: int,
    db: Session = Depends(get_db),
):
    """Добавить пользователя в группу."""
    org = _get_default_org(db)
    
    group = (
        db.query(GroupOfUsers)
        .filter(
            GroupOfUsers.id == group_id,
            GroupOfUsers.organization_id == org.id,
        )
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Проверяем дубликат
    from app.models import UserTerritoryMapping as UTM
    existing = (
        db.query(UTM)
        .filter(
            UTM.user_id == user_id,
            UTM.group_name == group.group_name,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Пользователь уже в группе")
    
    db.add(UTM(
        user_id=user_id,
        territory_id=group.territory_id,
        territory_name=group.territory_name,
        department_id=group.department_id,
        department_name=group.department_name,
        group_name=group.group_name,
        actual_position=user.actual_position,
    ))
    db.commit()
    
    return {"detail": f"Пользователь {user.fio} добавлен в группу {group.group_name}"}


@router.delete("/{group_id}/users/{user_id}")
def remove_user_from_group(
    group_id: int,
    user_id: int,
    db: Session = Depends(get_db),
):
    """Удалить пользователя из группы."""
    org = _get_default_org(db)
    
    group = (
        db.query(GroupOfUsers)
        .filter(
            GroupOfUsers.id == group_id,
            GroupOfUsers.organization_id == org.id,
        )
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    
    from app.models import UserTerritoryMapping as UTM
    mapping = (
        db.query(UTM)
        .filter(
            UTM.user_id == user_id,
            UTM.group_name == group.group_name,
        )
        .first()
    )
    if mapping:
        db.delete(mapping)
        db.commit()
    
    return {"detail": f"Пользователь удалён из группы {group.group_name}"}


# ==================== Фото ====================

@router.get("/photos")
def list_photos(folder: str | None = None):
    """Список фото из @Files/UpLoad/Foto."""
    photo_dir = _get_photo_dir()
    if not photo_dir.exists():
        return {"photos": [], "folder": str(photo_dir)}
    
    if folder:
        photo_dir = photo_dir / folder
    
    if not photo_dir.exists():
        return {"photos": [], "folder": str(photo_dir)}
    
    photos = []
    for f in sorted(photo_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
            photos.append({
                "name": f.name,
                "url": f"/api/groups/photos/{f.name}",
                "path": f"@Files/UpLoad/Foto/{f.name}",
            })
    
    return {"photos": photos, "folder": str(photo_dir)}


@router.get("/photos/{filename}")
def get_photo(filename: str):
    """Отдать фото по имени."""
    # Защита от path traversal
    if ".." in filename or filename.startswith("/"):
        raise HTTPException(status_code=400, detail="Недопустимое имя файла")
    
    photo_dir = _get_photo_dir()
    photo_path = photo_dir / filename
    
    # Безопасность: проверяем, что файл внутри photo_dir
    try:
        photo_path.relative_to(photo_dir)
    except ValueError:
        raise HTTPException(status_code=404, detail="Файл не найден")
    
    if not photo_path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    
    return FileResponse(
        str(photo_path),
        media_type="image/jpeg",
        filename=filename,
    )


@router.get("/photos/{folder}/{filename}")
def get_photo_folder(folder: str, filename: str):
    """Отдать фото из подпапки."""
    # Защита от path traversal
    if ".." in folder or ".." in filename or folder.startswith("/"):
        raise HTTPException(status_code=400, detail="Недопустимое имя папки")
    
    photo_dir = _get_photo_dir()
    photo_path = photo_dir / folder / filename
    
    # Безопасность: проверяем, что файл внутри photo_dir
    try:
        photo_path.relative_to(photo_dir)
    except ValueError:
        raise HTTPException(status_code=404, detail="Файл не найден")
    
    if not photo_path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    
    media_type = "image/jpeg"
    if filename.lower().endswith(".png"):
        media_type = "image/png"
    elif filename.lower().endswith(".gif"):
        media_type = "image/gif"
    elif filename.lower().endswith(".webp"):
        media_type = "image/webp"
    
    return FileResponse(
        str(photo_path),
        media_type=media_type,
        filename=filename,
    )
