"""Тесты роли «Экономист»: изменение ЧТС, история, контроль незаполненных ставок, RBAC."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import sessionmaker

from app.models import Employee, RateHistory, User, UserRole
from app.security import create_access_token


def _h(user):
    return {"Authorization": "Bearer " + create_access_token(user)}


def _make_economist(db_engine, seed, tab="EC-1", fio="Экономист Тест"):
    Session = sessionmaker(bind=db_engine, expire_on_commit=False, autoflush=False, autocommit=False)
    db = Session()
    eco = User(
        organization_id=seed["org"].id,
        tab_no=tab,
        fio=fio,
        role=UserRole.economist,
        status="Активен",
        password_hash="x",
        must_change_password=False,
    )
    db.add(eco)
    db.commit()
    headers = _h(eco)  # токен до закрытия сессии (атрибуты ещё доступны)
    db.close()
    return headers


def _economist_from_id(db_engine, user_id):
    """Headers экономиста по id (для тестов, где объект уже detached)."""
    Session = sessionmaker(bind=db_engine, expire_on_commit=False, autoflush=False, autocommit=False)
    db = Session()
    eco = db.get(User, user_id)
    headers = _h(eco) if eco else {}
    db.close()
    return headers


def _get_emp(db_engine, emp_id) -> Employee:
    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    db = Session()
    emp = db.get(Employee, emp_id)
    db.close()
    return emp


def test_economist_updates_rate_and_writes_history(client, db_engine, seed):
    eco_headers = _make_economist(db_engine, seed)
    Session = sessionmaker(bind=db_engine, expire_on_commit=False, autoflush=False, autocommit=False)
    db = Session()
    eco_id = (
        db.query(User).filter(User.tab_no == "EC-1", User.organization_id == seed["org"].id).first().id
    )
    db.close()

    changed_at = date(2026, 8, 20)
    r = client.post(
        "/api/economist/update-rate",
        headers=eco_headers,
        json={"tab_no": "E-1", "changed_at": changed_at.isoformat(), "new_rate": 415.5, "comment": "Повышение"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["hourly_rate"] == 415.5
    assert body["rate_last_raised"] == "2026-08-20"
    assert body["fio"] == "Иванов Иван"

    emp = _get_emp(db_engine, seed["emp1"].id)
    assert emp.hourly_rate == 415.5
    assert emp.rate_last_raised == changed_at

    # Запись в RateHistory создана.
    Session2 = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    db2 = Session2()
    hist = db2.query(RateHistory).filter(RateHistory.employee_id == seed["emp1"].id).all()
    db2.close()
    assert len(hist) == 1
    assert hist[0].old_rate is None
    assert hist[0].new_rate == 415.5
    assert hist[0].changed_by_user_id == eco_id


def test_economist_rate_history_endpoint(client, db_engine, seed):
    eco_headers = _make_economist(db_engine, seed)

    for new_rate in (400.0, 430.25):
        resp = client.post(
            "/api/economist/update-rate",
            headers=eco_headers,
            json={"tab_no": "E-1", "changed_at": date(2026, 7, 15).isoformat(), "new_rate": new_rate},
        )
        assert resp.status_code == 200, resp.text

    r = client.get(f"/api/economist/rate-history?employee_id={seed['emp1'].id}", headers=eco_headers)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 2
    assert rows[0]["new_rate"] == 430.25  # новейшая запись первой (одинаковая дата → по id desc)
    assert rows[0]["old_rate"] == 400.0


def test_economist_missing_rates_badge(client, db_engine, seed):
    eco_headers = _make_economist(db_engine, seed)

    r = client.get("/api/economist/missing-rates", headers=eco_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 2
    tabs = {item["tab_no"] for item in body["items"]}
    assert "E-1" in tabs and "E-2" in tabs

    # После заполнения ЧТС сотрудник исчезает из списка незаполненных.
    resp = client.post(
        "/api/economist/update-rate",
        headers=eco_headers,
        json={"tab_no": "E-1", "changed_at": date(2026, 8, 1).isoformat(), "new_rate": 390.0},
    )
    assert resp.status_code == 200
    r2 = client.get("/api/economist/missing-rates", headers=eco_headers)
    tabs2 = {item["tab_no"] for item in r2.json()["items"]}
    assert "E-1" not in tabs2
    assert "E-2" in tabs2


def test_economist_rbac_denied_for_other_roles(client, db_engine, seed):
    # Мастер не имеет доступа к роутеру экономиста.
    r = client.get("/api/economist/missing-rates", headers=_h(seed["master"]))
    assert r.status_code == 403

    eco_headers = _make_economist(db_engine, seed)

    # Экономист не имеет доступа к админ-эндпоинтам.
    r2 = client.get("/api/admin/users", headers=eco_headers)
    assert r2.status_code == 403


def test_economist_rate_history_idor_other_org(client, db_engine, seed):
    """Экономист из другой организации не видит историю чужого сотрудника (404)."""
    Session = sessionmaker(bind=db_engine, expire_on_commit=False, autoflush=False, autocommit=False)
    db = Session()
    other_org = __import__("app.models", fromlist=["Organization"]).Organization(
        code="other", name="Чужая ОП"
    )
    db.add(other_org)
    db.flush()
    eco = User(
        organization_id=other_org.id,
        tab_no="EC-X",
        fio="Чужой экономист",
        role=UserRole.economist,
        status="Активен",
        password_hash="x",
        must_change_password=False,
    )
    db.add(eco)
    db.commit()
    headers = _h(eco)  # токен до закрытия сессии
    db.close()

    r = client.get(
        f"/api/economist/rate-history?employee_id={seed['emp1'].id}", headers=headers
    )
    assert r.status_code == 404


def test_economist_update_rate_no_changes(client, db_engine, seed):
    eco_headers = _make_economist(db_engine, seed)

    # Первый раз — успех.
    first = client.post(
        "/api/economist/update-rate",
        headers=eco_headers,
        json={"tab_no": "E-1", "changed_at": date(2026, 8, 1).isoformat(), "new_rate": 400.0},
    )
    assert first.status_code == 200

    # Повтор той же ставки и даты — «нет изменений».
    second = client.post(
        "/api/economist/update-rate",
        headers=eco_headers,
        json={"tab_no": "E-1", "changed_at": date(2026, 8, 1).isoformat(), "new_rate": 400.0},
    )
    assert second.status_code == 400

    # Смена даты при той же ставке — допустимо (фиксация даты повышения задним числом).
    third = client.post(
        "/api/economist/update-rate",
        headers=eco_headers,
        json={"tab_no": "E-1", "changed_at": date(2026, 9, 1).isoformat(), "new_rate": 400.0},
    )
    assert third.status_code == 200