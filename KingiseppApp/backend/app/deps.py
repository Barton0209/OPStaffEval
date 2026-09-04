from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, UserRole
from app.security import decode_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация")
    payload = decode_token(creds.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный токен")
    user = db.get(User, int(payload["sub"]))
    if not user or user.status != "Активен":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь неактивен")
    return user


def touch_login(db: Session, user: User) -> None:
    """Обновляет last_login_at без commit — вызывающий код коммитит сам."""
    user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(user)


def require_roles(*roles: UserRole):
    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
        return user

    return _dep
