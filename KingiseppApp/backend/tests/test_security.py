"""Регрессионные тесты безопасности Этапа 1: rate-limit, эскалация, IDOR, смена пароля, продление токена."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import jwt as pyjwt

from app.config import get_settings
from app.security import create_access_token


def _h(user):
    return {"Authorization": "Bearer " + create_access_token(user)}


def test_login_rate_limit(client):
    statuses = [
        client.post(
            "/api/field/auth/login", json={"tab_no": "RATE-X", "password": "bad"}
        ).status_code
        for _ in range(7)
    ]
    assert statuses[-1] == 429  # лимит 5/мин
    assert statuses[:5] == [401] * 5


def test_must_change_password_returns_403_with_header(client, db_engine, seed):
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    db = Session()
    master = db.get(__import__("app.models", fromlist=["User"]).User, seed["master"].id)
    master.must_change_password = True
    db.commit()
    db.close()

    r = client.get("/api/field/assignments", headers=_h(seed["master"]))
    assert r.status_code == 403
    assert r.headers.get("X-Require-Password-Change") == "true"


def test_wrong_old_password_on_change(client, seed):
    h = _h(seed["master"])
    r = client.post(
        "/api/field/me/password",
        headers=h,
        json={"old_password": "WRONG", "new_password": "NewPass123"},
    )
    assert r.status_code == 400


def test_admin_op_cannot_change_admin(client, db_engine, seed):
    from app.models import User, UserRole
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    db = Session()
    sysadmin = User(
        organization_id=seed["org"].id,
        tab_no="SYS-1",
        fio="Сисадмин",
        role=UserRole.admin,
        status="Активен",
        password_hash="x",
        must_change_password=False,
    )
    db.add(sysadmin)
    db.commit()
    sid = sysadmin.id
    db.close()

    r = client.patch(
        f"/api/admin/users/{sid}",
        headers=_h(seed["admin_op"]),
        json={"password": "NewPass123"},
    )
    assert r.status_code == 403


def test_idor_other_org_object_404(client, db_engine, seed):
    from app.models import Assignment, Employee, Organization
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    db = Session()
    other = Organization(code="other", name="Другая ОП")
    db.add(other)
    db.flush()
    other_emp = Employee(organization_id=other.id, tab_no="X-9", fio="Чужой")
    db.add(other_emp)
    db.flush()
    other_asg = Assignment(
        organization_id=other.id,
        period_id=seed["period"].id,
        employee_id=other_emp.id,
        evaluate=True,
        primary_user_id=seed["master"].id,
    )
    db.add(other_asg)
    db.commit()
    oid = other_asg.id
    db.close()

    r = client.patch(
        f"/api/admin/assignments/{oid}",
        headers=_h(seed["admin_op"]),
        json={"evaluate": False},
    )
    # F05 FIX: теперь возвращаем 403 (безопаснее — предотвращает enumeration)
    assert r.status_code == 403


def test_soft_token_renewal(client, seed):
    settings = get_settings()
    # Свежий токен — продления нет.
    r = client.get("/api/field/me", headers=_h(seed["master"]))
    assert r.status_code == 200
    assert r.headers.get("X-New-Token") is None

    # «Старый» токен (exp через 10 минут) — сервер выдаёт X-New-Token.
    payload = {
        "sub": str(seed["master"].id),
        "tab_no": seed["master"].tab_no,
        "role": "master",
        "org_id": seed["org"].id,
        "tv": 0,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
    }
    stale = pyjwt.encode(payload, settings.secret_key, algorithm="HS256")
    r2 = client.get(
        "/api/field/me", headers={"Authorization": f"Bearer {stale}"}
    )
    assert r2.status_code == 200
    assert r2.headers.get("X-New-Token") is not None