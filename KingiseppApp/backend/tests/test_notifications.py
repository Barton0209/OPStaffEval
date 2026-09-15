"""Тесты уведомлений: счётчик неоценённых анкет."""
from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from app.models import Assignment
from app.security import create_access_token


def _h(user):
    return {"Authorization": "Bearer " + create_access_token(user)}


def test_notifications_zero_when_all_submitted(client, seed):
    """Мастер сдал обе свои анкеты — бейдж 0."""
    r = client.get("/api/notifications", headers=_h(seed["master"]))
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0
    assert body["items"] == []


def test_notifications_counts_unsubmitted(client, db_engine, seed):
    """Прораб не сдал E-2 — бейдж 1. Мастер с новым закреплением — бейдж 1."""
    r = client.get("/api/notifications", headers=_h(seed["foreman"]))
    assert r.status_code == 200
    assert r.json()["count"] == 1

    # Новый период + закрепление E-2 за мастером без оценки → мастер видит 1 неоценённую.
    from app.models import Employee, EvaluationPeriod

    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    db = Session()
    emp3 = Employee(
        organization_id=seed["org"].id, tab_no="E-3", fio="Сидоров Сидр", territory="Участок А"
    )
    db.add(emp3)
    db.flush()
    p2 = EvaluationPeriod(
        organization_id=seed["org"].id, code="TEST-H3", title="Тест 3", is_open=True
    )
    db.add(p2)
    db.flush()
    db.add(
        Assignment(
            organization_id=seed["org"].id,
            period_id=p2.id,
            employee_id=emp3.id,
            site_name="Участок А",
            evaluate=True,
            primary_user_id=seed["master"].id,
            version=1,
        )
    )
    db.commit()
    db.close()

    r2 = client.get("/api/notifications", headers=_h(seed["master"]))
    assert r2.status_code == 200
    body = r2.json()
    assert body["count"] == 1
    assert body["items"][0]["fio"] == "Сидоров Сидр"
    assert body["items"][0]["my_role"] == "primary"


def test_notifications_secondary_role(client, db_engine, seed):
    """Пользователь как 2-й оценщик тоже получает уведомление."""
    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    db = Session()
    asg = db.get(Assignment, seed["asg2"].id)
    asg.dual_enabled = True
    asg.secondary_user_id = seed["master"].id
    db.commit()
    db.close()

    r = client.get("/api/notifications", headers=_h(seed["master"]))
    assert r.status_code == 200
    body = r.json()
    # У мастера E-1 сдан, E-2 как 2-й оценщик не сдан.
    assert body["count"] == 1
    assert body["items"][0]["assignment_id"] == seed["asg2"].id
    assert body["items"][0]["my_role"] == "secondary"