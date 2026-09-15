"""Тесты поведения GET /api/field/site-overview (site_overview для начальника участка)."""
from __future__ import annotations

from app.security import create_access_token


def _h(user):
    return {"Authorization": "Bearer " + create_access_token(user)}


def test_chief_overview_counts(client, seed):
    r = client.get("/api/field/site-overview", headers=_h(seed["chief"]))
    assert r.status_code == 200
    body = r.json()
    assert body["site_name"] == "Участок А"
    assert body["total"] == 1  # только свой участок
    assert body["masters"] and body["masters"][0]["tab_no"] == "M-1001"
    assert body["masters"][0]["submitted"] == 1
    assert body["masters"][0]["remaining"] == 0
    assert body["evaluation_started_on"] is not None


def test_chief_other_site_sees_nothing(client, db_engine, seed):
    TestingSessionLocal = __import__("sqlalchemy.orm", fromlist=["sessionmaker"]).sessionmaker(
        bind=db_engine, autoflush=False, autocommit=False
    )
    db = TestingSessionLocal()
    chief = db.get(__import__("app.models", fromlist=["User"]).User, seed["chief"].id)
    chief.site_name = "Участок В"
    db.commit()
    db.close()

    r = client.get("/api/field/site-overview", headers=_h(seed["chief"]))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["masters"] == []


def test_chief_without_site_gets_warning(client, db_engine, seed):
    TestingSessionLocal = __import__("sqlalchemy.orm", fromlist=["sessionmaker"]).sessionmaker(
        bind=db_engine, autoflush=False, autocommit=False
    )
    db = TestingSessionLocal()
    chief = db.get(__import__("app.models", fromlist=["User"]).User, seed["chief"].id)
    chief.site_name = None
    db.commit()
    db.close()

    r = client.get("/api/field/site-overview", headers=_h(seed["chief"]))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["warning"]


def test_chief_cannot_access_other_site_data(client, seed):
    """Начальник не должен получать назначения чужого участка (E-2) в сводке."""
    r = client.get("/api/field/site-overview", headers=_h(seed["chief"]))
    assert r.status_code == 200
    body = r.json()
    # единственное назначение его участка — E-1; общее число по участку равно 1.
    assert body["total"] == 1