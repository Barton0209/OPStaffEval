"""API для каскадного входа «Контроль»: Territory → Role → Users → Login → Setup Password."""

from datetime import datetime, timezone
import hmac

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.config import get_settings
from app.db import get_db
from app.models import (
    Department,
    GroupOfUsers,
    Organization,
    PasswordSetupCode,
    Territory,
    User,
    UserRole,
    UserStatus,
    UserTerritoryMapping,
)
from app.rate_limit import limiter
from app.schemas import TokenOut
from app.security import (
    create_access_token,
    decode_token,
    hash_password,
    hash_password_setup_code,
    verify_password,
)

router = APIRouter(prefix="/api/auth/control", tags=["auth_control"])
settings = get_settings()


class PasswordSetupIn(BaseModel):
    user_id: int
    code: str = Field(min_length=6, max_length=32)
    new_password: str = Field(min_length=8, max_length=128)


class ControlLoginIn(BaseModel):
    tab_no: str = Field(min_length=1, max_length=64)
    password: str | None = Field(default=None, max_length=72)


# Роли, доступные в каскаде
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


def _get_default_org(db: Session) -> Organization:
    org = db.query(Organization).first()
    if not org:
        org = Organization(code="kingisepp", name="Кингисепп (ВСМ)")
        db.add(org)
        db.flush()
    return org


# ==================== Площадки ====================

TERRITORIES = [
    "ОП Горно-Алтайск",
    "ОП Карелия.Садовый Дом № 1/Дом № 2",
    "ОП Кутузовский Сбер К32",
    "ОП Кингисепп-2.ЕвроХим",
    "ОП Геленджик Винный город",
    "ОП Геленджик Марина",
    "Центральный офис компании (ОКиТ)",
    "Центральный офис компании (Адаптация)",
    "Центральный офис компании (ОТиЗ)",
]


@router.get("/territories")
def list_territories(db: Session = Depends(get_db)):
    """Список площадок для входа."""
    org = _get_default_org(db)
    # Загружаем из БД, если есть
    db_territories = (
        db.query(Territory)
        .filter(Territory.organization_id == org.id, Territory.is_active.is_(True))
        .order_by(Territory.name)
        .all()
    )
    if db_territories:
        return [{"code": t.code, "name": t.name} for t in db_territories]
    # Fallback: хардкод список
    return [{"code": t.lower().replace(" ", "_"), "name": t} for t in TERRITORIES]


# ==================== Отделы ====================

@router.get("/roles")
def list_roles(territory: str | None = None, db: Session = Depends(get_db)):
    """Список отделов, опционально отфильтрованный по площадке."""
    org = _get_default_org(db)
    
    if territory:
        # Ищем связки в БД
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
                    result.append({"code": g.department_name.lower().replace(" ", "_"), "name": g.department_name})
            if result:
                return result
    
    # Fallback: полный список
    return [{"code": code, "name": name} for name, code in CONTROL_ROLES]


# ==================== Пользователи ====================

@router.get("/users")
def list_users(territory: str, role: str, db: Session = Depends(get_db)):
    """Список пользователей для выбранной площадки и отдела."""
    org = _get_default_org(db)
    
    # Нормализуем role
    role_map = {name: code for name, code in CONTROL_ROLES}
    system_role = role_map.get(role)
    
    if not system_role:
        return []
    
    users = (
        db.query(User)
        .filter(
            User.organization_id == org.id,
            User.role == system_role,
            User.status == UserStatus.active,
        )
        .order_by(User.fio)
        .all()
    )
    
    return [
        {
            "id": u.id,
            "tab_no": u.tab_no,
            "fio": u.fio,
        }
        for u in users
    ]


# ==================== Вход ====================

@router.post("/login")
@limiter.limit("5/minute")
def control_login(
    request: Request,
    payload: ControlLoginIn,
    db: Session = Depends(get_db),
):
    """Вход по tab_no. Если пароль не установлен — переход к setup."""
    user = (
        db.query(User)
        .filter(User.tab_no == payload.tab_no.strip(), User.status == UserStatus.active)
        .first()
    )
    
    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    
    # Проверяем, установлен ли пароль
    has_password = bool(user.password_hash and user.password_hash != "")
    
    if not has_password:
        # Первый вход — нужен setup пароля
        return {
            "requires_password_setup": True,
            "user": {
                "id": user.id,
                "tab_no": user.tab_no,
                "fio": user.fio,
                "role": user.role.value,
                "organization_id": user.organization_id,
            },
        }
    
    # Если пароль есть, но не передан — тоже запрос setup
    if not payload.password:
        return {
            "requires_password_setup": True,
            "user": {
                "id": user.id,
                "tab_no": user.tab_no,
                "fio": user.fio,
                "role": user.role.value,
                "organization_id": user.organization_id,
            },
        }
    
    # Обычная проверка пароля
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный пароль")
    
    if user.must_change_password:
        # Временный пароль — нужно сменить
        token = create_access_token(user)
        return {
            "requires_password_setup": True,
            "access_token": token,
            "user": {
                "id": user.id,
                "tab_no": user.tab_no,
                "fio": user.fio,
                "role": user.role.value,
                "organization_id": user.organization_id,
            },
        }
    
    # Успешный вход
    token = create_access_token(user)
    return {
        "requires_password_setup": False,
        "access_token": token,
        "user": {
            "id": user.id,
            "tab_no": user.tab_no,
            "fio": user.fio,
            "role": user.role.value,
            "organization_id": user.organization_id,
            "must_change_password": user.must_change_password,
        },
    }


# ==================== Создание пароля ====================

@router.post("/setup-password")
@limiter.limit("3/minute")
def setup_password(
    request: Request,
    payload: PasswordSetupIn,
    db: Session = Depends(get_db),
):
    """Consume an administrator-issued one-time code and set a new password."""
    user = db.get(User, payload.user_id)
    if not user or user.status != UserStatus.active or not user.must_change_password:
        raise HTTPException(status_code=403, detail="Установка пароля недоступна")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    setup_code = (
        db.query(PasswordSetupCode)
        .filter(
            PasswordSetupCode.user_id == user.id,
            PasswordSetupCode.consumed_at.is_(None),
        )
        .order_by(PasswordSetupCode.id.desc())
        .first()
    )
    supplied_hash = hash_password_setup_code(user.id, payload.code.strip())
    if (
        not setup_code
        or setup_code.expires_at <= now
        or setup_code.attempts >= setup_code.max_attempts
        or not hmac.compare_digest(setup_code.code_hash, supplied_hash)
    ):
        if setup_code and setup_code.expires_at > now and setup_code.attempts < setup_code.max_attempts:
            setup_code.attempts += 1
            db.commit()
        raise HTTPException(status_code=403, detail="Код недействителен или истёк")

    setup_code.consumed_at = now
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    # F03 FIX: увеличиваем token_version
    user.token_version = (user.token_version or 0) + 1
    
    db.commit()
    
    # Автоматический вход
    token = create_access_token(user)
    return {
        "access_token": token,
        "user": {
            "id": user.id,
            "tab_no": user.tab_no,
            "fio": user.fio,
            "role": user.role.value,
            "organization_id": user.organization_id,
            "must_change_password": False,
        },
    }


# ==================== Забыли пароль ====================

@router.post("/forgot-password")
@limiter.limit("3/minute")
def forgot_password(request: Request, tab_no: str, db: Session = Depends(get_db)):
    """Запрос сброса пароля — ответ нейтральный (без раскрытия информации)."""
    user = (
        db.query(User)
        .filter(User.tab_no == tab_no.strip())
        .first()
    )
    # Всегда возвращаем успешный ответ — чтобы не раскрывать наличие пользователя
    return {"message": "Если пользователь существует, обратитесь к Администрации ОП для сброса пароля"}
