from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import admin, field, registry
from app.config import get_settings
from app.db import Base, SessionLocal, engine
from app.models import User, UserRole
from app.scheduler import start_scheduler, stop_scheduler
from app.security import hash_password
from app.services.imports import ensure_org_and_period

settings = get_settings()


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
        chief = (
            db.query(User)
            .filter(User.organization_id == org.id, User.tab_no == "CHIEF-OP")
            .first()
        )
        if not chief:
            db.add(
                User(
                    organization_id=org.id,
                    tab_no="CHIEF-OP",
                    fio="Начальник участка (пилот)",
                    role=UserRole.site_chief,
                    status="Активен",
                    password_hash=hash_password("ChiefOP2026"),
                )
            )
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _ensure_bootstrap_admin()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.cors_origins == "*" else settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(field.router)
app.include_router(admin.router)
app.include_router(registry.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name, "org": settings.org_name}


dist = settings.frontend_dist
if dist.exists():
    assets = dist / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.middleware("http")
    async def spa_fallback(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/api"):
            return response
        if request.method != "GET" or response.status_code != 404:
            return response
        # Не отдаём HTML на отсутствующие API — только на страницы UI
        candidate = dist / path.lstrip("/")
        if path != "/" and candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        index = dist / "index.html"
        if index.exists():
            return FileResponse(index)
        return response

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
