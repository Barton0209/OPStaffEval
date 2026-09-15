from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(APP_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "KingiseppApp"
    org_code: str = "kingisepp"
    org_name: str = "Кингисепп (ВСМ)"
    secret_key: str = ""
    access_token_expire_minutes: int = 60
    # Мягкое продление: если до истечения токена осталось меньше минут — выдать X-New-Token.
    token_renew_before_minutes: int = 30
    database_url: str = ""
    host: str = "127.0.0.1"
    port: int = 8000
    files_dir: str = str((APP_ROOT.parent / "Files").resolve())
    cors_origins: str = ""
    cors_origin_regex: str = ""
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    expose_docs: bool = False
    max_upload_mb: int = 10

    def model_post_init(self, __context) -> None:  # noqa: ANN001
        if not self.database_url.strip():
            db_path = (APP_ROOT / "data" / "kingisepp.db").resolve().as_posix()
            object.__setattr__(self, "database_url", f"sqlite:///{db_path}")
        if not self.secret_key.strip() or len(self.secret_key) < 32:
            raise ValueError(
                "SECRET_KEY не задан или слишком слабый (< 32 символов). Сгенерируйте новый:\n"
                '  python -c "import secrets; print(secrets.token_hex(32))"\n'
                "и укажите его в .env (SECRET_KEY=...)."
            )

    @property
    def data_dir(self) -> Path:
        p = APP_ROOT / "data"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def logs_dir(self) -> Path:
        p = APP_ROOT / "logs"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def frontend_dist(self) -> Path:
        return APP_ROOT / "frontend" / "dist"

    @property
    def files_path(self) -> Path:
        return Path(self.files_dir)


@lru_cache
def get_settings() -> Settings:
    return Settings()
