from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"
settings = get_settings()


def hash_password(password: str) -> str:
    return pwd_context.hash(password[:72])


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain[:72], hashed)


def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user.id),
        "tab_no": user.tab_no,
        "role": user.role.value,
        "org_id": user.organization_id,
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return None


def authenticate_user(db: Session, tab_no: str, password: str) -> User | None:
    user = (
        db.query(User)
        .filter(User.tab_no == tab_no.strip(), User.status == "Активен")
        .first()
    )
    if not user or not verify_password(password, user.password_hash):
        return None
    return user
