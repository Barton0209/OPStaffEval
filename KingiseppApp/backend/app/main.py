import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.api import admin, admin_imports, auth_control, economist, exports, field, groups, notifications, registry, summary
from app.config import get_settings
from app.db import SessionLocal, engine
from app.logging_setup import setup_logging
from app.migrate import run_migrations
from app.models import User, UserRole, UserStatus
from app.rate_limit import limiter
from app.scheduler import start_scheduler, stop_scheduler
from app.security import (
    generate_temporary_password,
    hash_password,
    renew_access_token_if_needed,
)
from app.services.imports import ensure_org_and_period

settings = get_settings()
logger = logging.getLogger(__name__)


def _ensure_bootstrap_admin() -> None:
    db = SessionLocal()
    try:
        org, _period = ensure_org_and_period(db, settings.org_code, settings.org_name)
        admin = (
            db.query(User)
            .filter(User.organization_id == org.id, User.tab_no == "ADMIN-OP")
            .first()
        )
        if not admin:
            if not settings.admin_initial_password:
                logger.error("ADMIN-OP не создан: задайте ADMIN_INITIAL_PASSWORD и перезапустите приложение.")
                db.rollback()
                return
            db.add(
                User(
                    organization_id=org.id,
                    tab_no="ADMIN-OP",
                    fio="Администрация ОП",
                    role=UserRole.admin_op,
                    status=UserStatus.active,
                    password_hash=hash_password(settings.admin_initial_password),
                    must_change_password=True,
                )
            )
            logger.warning("Создана учётная запись ADMIN-OP из ADMIN_INITIAL_PASSWORD; значение не журналируется.")
            logger.warning("Обязательно смените пароль при первом входе.")
        chief = (
            db.query(User)
            .filter(User.organization_id == org.id, User.tab_no == "CHIEF-OP")
            .first()
        )
        if not chief:
            temp_pwd = generate_temporary_password()
            db.add(
                User(
                    organization_id=org.id,
                    tab_no="CHIEF-OP",
                    fio="Начальник участка (пилот)",
                    role=UserRole.site_chief,
                    status=UserStatus.active,
                    password_hash=hash_password(temp_pwd),
                    must_change_password=True,
                )
            )
            logger.warning("Создана учётная запись CHIEF-OP. Пароль выдан отдельно.")
            logger.warning("Обязательно смените пароль при первом входе.")
        db.commit()
    finally:
        db.close()


def _ensure_schema_columns() -> None:
    """create_all не добавляет колонки в существующие таблицы — ALTER вручную (идемпотентно)."""
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
        emp_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(employees)"))]
        if "rate_last_raised" not in emp_cols:
            conn.execute(text("ALTER TABLE employees ADD COLUMN rate_last_raised DATE"))
        if "citizenship" not in emp_cols:
            conn.execute(text("ALTER TABLE employees ADD COLUMN citizenship VARCHAR(64)"))
        if "category" not in emp_cols:
            conn.execute(text("ALTER TABLE employees ADD COLUMN category VARCHAR(64)"))
        if "probation_end_date" not in emp_cols:
            conn.execute(text("ALTER TABLE employees ADD COLUMN probation_end_date DATE"))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(settings.logs_dir)
    # Схема управляется Alembic (вместо Base.metadata.create_all).
    run_migrations()
    _ensure_schema_columns()
    _ensure_bootstrap_admin()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    docs_url="/docs" if settings.expose_docs else None,
    redoc_url="/redoc" if settings.expose_docs else None,
    openapi_url="/openapi.json" if settings.expose_docs else None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Явный белый список origin (+ маска для динамических доменов туннелей).
cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["http://localhost:5173"],
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    )
    return response


@app.middleware("http")
async def soft_token_renewal(request: Request, call_next):
    """Мягкое продление JWT: при TTL < token_renew_before_minutes отдаём X-New-Token."""
    response = await call_next(request)
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        renewed = renew_access_token_if_needed(
            auth[7:].strip(),
            threshold_minutes=settings.token_renew_before_minutes,
        )
        if renewed:
            response.headers["X-New-Token"] = renewed
    return response


app.include_router(field.router)
app.include_router(auth_control.router)
app.include_router(admin_imports.router)
app.include_router(summary.router)
app.include_router(exports.router)
app.include_router(admin.router)
app.include_router(economist.router)
app.include_router(notifications.router)
app.include_router(registry.router)
app.include_router(groups.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


dist = settings.frontend_dist
if dist.exists():
    assets = dist / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.middleware("http")
    async def spa_fallback(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if (
            path.startswith("/api")
            or path.startswith("/docs")
            or path.startswith("/redoc")
            or path == "/openapi.json"
        ):
            return response
        if request.method != "GET" or response.status_code != 404:
            return response
        # Безопасный fallback: только нормализованный путь внутри dist
        import pathlib
        pure = pathlib.PurePosixPath(path).relative_to("/")
        safe = pure.normalize()
        # Запрет traversal: путь не должен содержать ".." или выходить за пределы dist
        if ".." in str(pure) or str(safe).startswith(".."):
            return response
        candidate = dist / safe
        if not candidate.exists() or not candidate.is_file():
            return FileResponse(dist / "index.html")
        return FileResponse(candidate)

    @app.get("/")
    def spa_root():
        return FileResponse(dist / "index.html")
else:

    @app.get("/")
    def no_frontend():
        return JSONResponse(
            {"detail": "Frontend dist не собран. Выполните npm run build в frontend/"},
            status_code=503,
        )
