"""Общие фикстуры: изолированная in-memory БД + TestClient без запуска lifespan."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from datetime import datetime  # noqa: E402

from app.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Assignment,
    Employee,
    Evaluation,
    EvaluationPeriod,
    EvaluationStatus,
    Organization,
    User,
    UserRole,
)
from app.security import hash_password  # noqa: E402


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def client(db_engine):
    TestingSessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.state.limiter.reset()
    # Без `with` — lifespan (миграции/планировщик) не запускается.
    yield TestClient(app)
    app.state.limiter.reset()
    app.dependency_overrides.clear()


@pytest.fixture()
def seed(db_engine):
    """Минимальный набор данных для тестов ЛК мастера/начальника."""
    TestingSessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    db = TestingSessionLocal()

    org = Organization(code="kingisepp", name="Тест ОП")
    db.add(org)
    db.flush()
    period = EvaluationPeriod(
        organization_id=org.id, code="TEST-H2", title="Тест", is_open=True
    )
    db.add(period)
    db.flush()

    def make_user(tab, role, site):
        u = User(
            organization_id=org.id,
            tab_no=tab,
            fio=tab,
            role=role,
            site_name=site,
            status="Активен",
            password_hash=hash_password("Password123"),
            must_change_password=False,
        )
        db.add(u)
        db.flush()
        return u

    master = make_user("M-1001", UserRole.master, "Участок А")
    foreman = make_user("F-1002", UserRole.foreman, "Участок Б")
    chief = make_user("C-1003", UserRole.site_chief, "Участок А")
    admin_op = make_user("A-1004", UserRole.admin_op, None)

    emp1 = Employee(
        organization_id=org.id, tab_no="E-1", fio="Иванов Иван", territory="Участок А"
    )
    emp2 = Employee(
        organization_id=org.id, tab_no="E-2", fio="Петров Пётр", territory="Участок Б"
    )
    db.add_all([emp1, emp2])
    db.flush()

    asg1 = Assignment(
        organization_id=org.id,
        period_id=period.id,
        employee_id=emp1.id,
        site_name="Участок А",
        evaluate=True,
        primary_user_id=master.id,
        version=1,
    )
    asg2 = Assignment(
        organization_id=org.id,
        period_id=period.id,
        employee_id=emp2.id,
        site_name="Участок Б",
        evaluate=True,
        primary_user_id=foreman.id,
        version=1,
    )
    db.add_all([asg1, asg2])
    db.flush()

    ev1 = Evaluation(
        organization_id=org.id,
        assignment_id=asg1.id,
        employee_id=emp1.id,
        evaluator_id=master.id,
        evaluator_role=UserRole.master,
        score_quality=4,
        score_discipline=4,
        score_safety=4,
        score_skills=4,
        score_versatility=4,
        status=EvaluationStatus.submitted,
        submitted_at=datetime.now(),
    )
    db.add(ev1)
    db.commit()

    data = {
        "org": org,
        "period": period,
        "master": master,
        "foreman": foreman,
        "chief": chief,
        "admin_op": admin_op,
        "emp1": emp1,
        "emp2": emp2,
        "asg1": asg1,
        "asg2": asg2,
    }
    yield data
    db.close()
