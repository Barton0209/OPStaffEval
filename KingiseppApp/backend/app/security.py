import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User, UserStatus

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"
settings = get_settings()


def generate_temporary_password() -> str:
    """Одноразовый случайный пароль (12 символов, url-safe)."""
    return secrets.token_urlsafe(12)


def hash_password(password: str) -> str:
    """Хеширует пароль. bcrypt имеет внутренний лимит 72 символа,
    поэтому пароли длиннее 72 симвалов обрезаются — это ограничение алгоритма.
    Схемы валидации (schemas.py) ограничивают max_length=72 на входе."""
    return pwd_context.hash(password[:72])


def verify_password(plain: str, hashed: str) -> bool:
    """Проверяет пароль. См. примечание к hash_password."""
    return pwd_context.verify(plain[:72], hashed)


def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user.id),
        "tab_no": user.tab_no,
        "role": user.role.value,
        "org_id": user.organization_id,
        "tv": user.token_version or 0,
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return None


def renew_access_token_if_needed(token: str, threshold_minutes: int = 30) -> str | None:
    """Продлевает токен, если до истечения осталось меньше threshold_minutes. Иначе None."""
    payload = decode_token(token)
    if not payload:
        return None
    try:
        exp = int(payload.get("exp") or 0)
        remaining = exp - datetime.now(timezone.utc).timestamp()
    except (TypeError, ValueError):
        return None
    if not (0 < remaining < threshold_minutes * 60):
        return None
    payload["exp"] = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def authenticate_user(db: Session, tab_no: str, password: str) -> User | None:
    user = (
        db.query(User)
        .filter(User.tab_no == tab_no.strip(), User.status == UserStatus.active)
        .first()
    )
    if not user or not verify_password(password, user.password_hash):
        return None
    return user
