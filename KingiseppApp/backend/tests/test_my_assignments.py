"""Тесты поведения GET /api/field/assignments (my_assignments)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import jwt as pyjwt

from app.config import get_settings
from app.security import create_access_token


def _h(user):
    return {"Authorization": "Bearer " + create_access_token(user)}


def _token_for(uid: int, tab_no: str, role: str, org_id: int) -> str:
    settings = get_settings()
    payload = {
        "sub": str(uid),
        "tab_no": tab_no,
        "role": role,
        "org_id": org_id,
        "tv": 0,
        "exp": datetime.now(timezone.utc) + timedelta(hours=12),
    }
    return pyjwt.encode(payload, settings.secret_key, algorithm="HS256")


def test_master_sees_only_own_assignments(client, seed):
    r = client.get("/api/field/assignments", headers=_h(seed["master"]))
    assert r.status_code == 200
    items = r.json()
    tabs = [i["tab_no"] for i in items]
    assert "E-1" in tabs
    assert "E-2" not in tabs  # чужое назначение (foreman) не видно
    ev1 = next(i for i in items if i["tab_no"] == "E-1")
    assert ev1["evaluation_status"] == "submitted"
    assert ev1["my_role"] == "primary"
    assert ev1["assignment_id"] == seed["asg1"].id


def test_foreman_sees_his_pending_assignment(client, seed):
    r = client.get("/api/field/assignments", headers=_h(seed["foreman"]))
    assert r.status_code == 200
    items = r.json()
    tabs = [i["tab_no"] for i in items]
    assert "E-2" in tabs
    assert "E-1" not in tabs
    ev2 = next(i for i in items if i["tab_no"] == "E-2")
    assert ev2["evaluation_status"] is None  # ещё не заполнял


def test_user_without_assignments_gets_empty(client, db_engine, seed):
    from app.models import User, UserRole
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    db = Session()
    empty = User(
        organization_id=seed["org"].id,
        tab_no="M-7777",
        fio="Без назначений",
        role=UserRole.master,
        status="Активен",
        password_hash="x",
        must_change_password=False,
    )
    db.add(empty)
    db.commit()
    uid = empty.id
    db.close()

    token = _token_for(uid, "M-7777", "master", seed["org"].id)
    r = client.get("/api/field/assignments", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == []


def test_my_assignments_query_count_bounded(client, db_engine, seed):
    """Нет N+1: число SQL-запросов ограничено (batch-загрузка)."""
    from sqlalchemy import event

    counter = {"n": 0}

    @event.listens_for(db_engine, "before_cursor_execute")
    def _count(*args, **kwargs):  # noqa: ANN002,ANN003
        counter["n"] += 1

    try:
        r = client.get("/api/field/assignments", headers=_h(seed["master"]))
        assert r.status_code == 200
        assert counter["n"] <= 12, f"подозрение на N+1: {counter['n']} запросов"
    finally:
        event.remove(db_engine, "before_cursor_execute", _count)


def test_dual_peer_submitted_flag(client, db_engine, seed):
    """Dual-назначение: вторая анкета сдана — peer_submitted=true."""
    from app.models import Evaluation, EvaluationStatus
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    db = Session()
    asg2 = db.get(__import__("app.models", fromlist=["Assignment"]).Assignment, seed["asg2"].id)
    asg2.dual_enabled = True
    asg2.secondary_user_id = seed["chief"].id
    asg2.version = 2
    db.add(
        Evaluation(
            organization_id=seed["org"].id,
            assignment_id=asg2.id,
            employee_id=seed["emp2"].id,
            evaluator_id=seed["chief"].id,
            evaluator_role=seed["chief"].role,
            score_quality=3,
            score_discipline=3,
            score_safety=3,
            score_skills=3,
            score_versatility=3,
            status=EvaluationStatus.submitted,
        )
    )
    db.commit()
    db.close()

    r = client.get("/api/field/assignments", headers=_h(seed["foreman"]))
    assert r.status_code == 200
    items = r.json()
    row = next(i for i in items if i["tab_no"] == "E-2")
    assert row["peer_submitted"] is True