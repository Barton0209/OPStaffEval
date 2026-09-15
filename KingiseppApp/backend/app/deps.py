from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, UserRole, UserStatus
from app.security import decode_token

bearer = HTTPBearer(auto_error=False)

REQUIRE_PASSWORD_CHANGE_HEADER = "X-Require-Password-Change"


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def _get_payload_user(creds: HTTPAuthorizationCredentials | None, db: Session) -> User:
    if not creds:
        raise _unauthorized("Требуется авторизация")
    payload = decode_token(creds.credentials)
    if not payload or "sub" not in payload:
        raise _unauthorized("Неверный токен")
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise _unauthorized("Неверный токен") from None
    user = db.get(User, user_id)
    if not user or user.status != UserStatus.active:
        raise _unauthorized("Пользователь неактивен")
    # Инвалидация сессий при смене пароля: версия токена должна совпадать.
    if (payload.get("tv") or 0) != (user.token_version or 0):
        raise _unauthorized("Сессия устарела — выполните вход заново")
    return user


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    """Полная аутентификация + проверка обязательной смены пароля."""
    user = _get_payload_user(creds, db)
    if user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуется смена пароля",
            headers={REQUIRE_PASSWORD_CHANGE_HEADER: "true"},
        )
    return user


def get_current_user_allow_password_change(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    """Аутентификация без принудительной смены пароля (для /api/field/me/password)."""
    return _get_payload_user(creds, db)


def touch_login(db: Session, user: User) -> None:
    """Обновляет last_login_at без commit — вызывающий код коммитит сам."""
    # Храним aware-datetime (UTC) — модель должна использовать DateTime(timezone=True)
    user.last_login_at = datetime.now(timezone.utc)
    db.add(user)


def require_roles(*roles: UserRole):
    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
        return user

    return _dep
