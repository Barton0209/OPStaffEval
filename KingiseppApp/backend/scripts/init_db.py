"""Initialize DB and optionally import Excel files."""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.config import get_settings  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import User, UserRole  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.services.imports import (  # noqa: E402
    ensure_org_and_period,
    import_base,
    import_carnet,
    import_users,
    resolve_assignment_registry_path,
)


def main(do_import: bool = True) -> None:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        org, period = ensure_org_and_period(db, settings.org_code, settings.org_name)
        admin = db.query(User).filter(User.organization_id == org.id, User.tab_no == "ADMIN-OP").first()
        if not admin:
            db.add(
                User(
                    organization_id=org.id,
                    tab_no="ADMIN-OP",
                    fio="Администрация ОП",
                    role=UserRole.admin_op,
                    status="Активен",
                    password_hash=hash_password("AdminOP2026"),
                )
            )
            db.commit()
            print("Created ADMIN-OP / AdminOP2026")
        else:
            print("ADMIN-OP already exists")

        if do_import:
            files = settings.files_path
            base = files / "01_База_1С.xlsx"
            users = files / "02_Пользователи.xlsx"
            registry = resolve_assignment_registry_path(files)
            print("Import from", files)
            print(import_base(db, base, org))
            print(import_users(db, users, org))
            if registry:
                print(import_carnet(db, registry, org, period))
            else:
                print("SKIP: 03_Реестр_закрепления.xlsx not found")
    finally:
        db.close()
    print("DB ready:", settings.database_url)


if __name__ == "__main__":
    main(do_import="--no-import" not in sys.argv)
