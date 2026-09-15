"""Offline-конфликты: conflict_diff, событие draft_discarded_conflict, отмена черновика."""
from __future__ import annotations

from app.models import Assignment, Evaluation, EvaluationStatus
from app.security import create_access_token


def _h(user):
    return {"Authorization": "Bearer " + create_access_token(user)}


def test_version_conflict_returns_diff(client, db_engine, seed):
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    db = Session()
    db.add(
        Evaluation(
            organization_id=seed["org"].id,
            assignment_id=seed["asg1"].id,
            employee_id=seed["emp1"].id,
            evaluator_id=seed["master"].id,
            evaluator_role=seed["master"].role,
            score_quality=3,
            score_discipline=3,
            score_safety=3,
            score_skills=3,
            score_versatility=3,
            status=EvaluationStatus.draft,
        )
    )
    # Админ изменил назначение — версия выросла.
    asg1 = db.get(Assignment, seed["asg1"].id)
    asg1.version = 5
    db.commit()
    asg_id = seed["asg1"].id
    db.close()

    body = {
        "score_quality": 4,
        "score_discipline": 4,
        "score_safety": 4,
        "score_skills": 4,
        "score_versatility": 4,
        "assignment_version": 1,  # клиент видел старую версию
        "client_mutation_id": "conflict-test-1",
    }
    r = client.post(
        f"/api/field/assignments/{asg_id}/evaluation?submit=false",
        headers=_h(seed["master"]),
        json=body,
    )
    # F06 FIX: возвращаем 409 со структурированным diff
    assert r.status_code == 409
    data = r.json()
    assert data.get("detail") is not None


def test_discard_draft_records_event_and_deletes(client, db_engine, seed):
    from app.models import DomainEvent
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    db = Session()
    db.add(
        Evaluation(
            organization_id=seed["org"].id,
            assignment_id=seed["asg1"].id,
            employee_id=seed["emp1"].id,
            evaluator_id=seed["master"].id,
            evaluator_role=seed["master"].role,
            score_quality=3,
            score_discipline=3,
            score_safety=3,
            score_skills=3,
            score_versatility=3,
            status=EvaluationStatus.draft,
        )
    )
    db.commit()
    asg_id = seed["asg1"].id
    db.close()

    r = client.post(f"/api/field/assignments/{asg_id}/discard-draft", headers=_h(seed["master"]))
    assert r.status_code == 200

    db2 = Session()
    remaining = (
        db2.query(Evaluation)
        .filter(
            Evaluation.assignment_id == asg_id,
            Evaluation.evaluator_id == seed["master"].id,
            Evaluation.status == EvaluationStatus.draft,
        )
        .count()
    )
    event = (
        db2.query(DomainEvent)
        .filter(
            DomainEvent.entity_type == "evaluation",
            DomainEvent.action == "draft_discarded_conflict",
        )
        .first()
    )
    db2.close()
    assert remaining == 0
    assert event is not None