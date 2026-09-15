"""Initialize DB and optionally import Excel files."""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import text  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.migrate import run_migrations  # noqa: E402
from app.models import User, UserRole  # noqa: E402
from app.security import generate_temporary_password, hash_password  # noqa: E402
from app.services.imports import (  # noqa: E402
    ensure_org_and_period,
    import_base_v2,
    import_daily_v2,
    import_users_v2,
    import_registry_scores,
)


def _ensure_schema_columns() -> None:
    """Идемпотентное добавление колонок в существующую таблицу users."""
    with engine.begin() as conn:
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(users)"))]
        if not cols:
            return
        if "must_change_password" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN must_change_password "
                    "BOOLEAN NOT NULL DEFAULT 1"
                )
            )
        if "token_version" not in cols:
            conn.execute(
                text("ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0")
            )


def main(do_import: bool = True) -> None:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    # Схема управляется Alembic (вместо Base.metadata.create_all).
    run_migrations()
    _ensure_schema_columns()
    db = SessionLocal()
    try:
        org, period = ensure_org_and_period(db, settings.org_code, settings.org_name)
        admin = db.query(User).filter(User.organization_id == org.id, User.tab_no == "ADMIN-OP").first()
        if not admin:
            temp_pwd = generate_temporary_password()
            db.add(
                User(
                    organization_id=org.id,
                    tab_no="ADMIN-OP",
                    fio="Администрация ОП",
                    role=UserRole.admin_op,
                    status="Активен",
                    password_hash=hash_password(temp_pwd),
                    must_change_password=True,
                )
            )
            db.commit()
            print(f"Created ADMIN-OP. Временный пароль (смените при первом входе): {temp_pwd}")
        else:
            print("ADMIN-OP already exists")

        if do_import:
            files = settings.files_path / "UpLoad"
            base = files / "01_Base" / "01_База_1С.xlsx"
            daily = files / "02_Daily_report" / "02_Ежедневный_учёт.xlsx"
            users = files / "03_Users_Role_Permision" / "02_Пользователи.xlsx"
            registry = files / "05_Old_rating_register" / "03_Реестр_закрепления.xlsx"
            print("Import from", files)

            if base.exists():
                print("Importing base data...")
                print(import_base_v2(db, base, org))
            else:
                print(f"SKIP: {base} not found")

            if daily.exists():
                print("Importing daily report...")
                print(import_daily_v2(db, daily, org, period))
            else:
                print(f"SKIP: {daily} not found")

            if users.exists():
                print("Importing users...")
                print(import_users_v2(db, users, org))
            else:
                print(f"SKIP: {users} not found")

            if registry.exists():
                print("Importing registry scores...")
                print(import_registry_scores(db, registry, org, period))
            else:
                print(f"SKIP: {registry} not found")
    finally:
        db.close()
    print("DB ready:", settings.database_url)


if __name__ == "__main__":
    main(do_import="--no-import" not in sys.argv)
