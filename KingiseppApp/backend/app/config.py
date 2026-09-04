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
    secret_key: str = "change-me-in-production-kingisepp-2026"
    access_token_expire_minutes: int = 720
    database_url: str = ""
    host: str = "127.0.0.1"
    port: int = 8000
    files_dir: str = str((APP_ROOT.parent / "Files").resolve())
    cors_origins: str = "*"

    def model_post_init(self, __context) -> None:  # noqa: ANN001
        if not self.database_url.strip():
            db_path = (APP_ROOT / "data" / "kingisepp.db").resolve().as_posix()
            object.__setattr__(self, "database_url", f"sqlite:///{db_path}")

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
