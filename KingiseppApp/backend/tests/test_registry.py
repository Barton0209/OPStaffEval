"""Тесты реестра: probation-индикатор и строгий запрет чужих оценок для site_chief."""
from __future__ import annotations

from datetime import date, timedelta
from sqlalchemy.orm import sessionmaker

from app.models import Employee
from app.security import create_access_token


def _h(user):
    return {"Authorization": "Bearer " + create_access_token(user)}


def _set_probation(db_engine, emp_id, end_date: date):
    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    db = Session()
    emp = db.get(Employee, emp_id)
    emp.probation_end_date = end_date
    db.commit()
    db.close()


def test_registry_rows_have_probation_fields(client, db_engine, seed):
    """Реестр отдаёт дату окончания испытательного срока и признак активности."""
    _set_probation(db_engine, seed["emp1"].id, date.today() + timedelta(days=30))
    _set_probation(db_engine, seed["emp2"].id, date.today() - timedelta(days=10))

    r = client.get("/api/registry/rows", headers=_h(seed["admin_op"]))
    assert r.status_code == 200
    rows = {row["employee_id"]: row for row in r.json()}
    assert rows[seed["emp1"].id]["probation_active"] is True
    assert rows[seed["emp1"].id]["probation_end_date"] is not None
    assert rows[seed["emp2"].id]["probation_active"] is False


def test_registry_chief_sees_only_final_score(client, seed):
    """Начальник участка видит итоговый балл, но не чужие оценки/оценщиков."""
    r = client.get("/api/registry/rows", headers=_h(seed["chief"]))
    assert r.status_code == 200
    body = r.json()
    # Участок А → только E-1.
    assert len(body) == 1
    row = body[0]
    assert row["fio"] == "Иванов Иван"
    assert row["final_score"] is not None  # итоговая оценка видна
    assert row["primary_fio"] is None
    assert row["primary_avg"] is None
    assert row["secondary_fio"] is None
    assert row["secondary_avg"] is None
    assert row["combined_avg"] is None


def test_registry_questionnaire_chief_masked_others(client, db_engine, seed):
    """В анкете начальник видит полные данные только по своей оценке (если он оценщик)."""
    # E-1 оценивает мастер (не chief) — чужие баллы скрыты.
    r = client.get(
        f"/api/registry/questionnaire/{seed['asg1'].id}", headers=_h(seed["chief"])
    )
    assert r.status_code == 200
    q = r.json()
    assert q["final_score"] is not None
    # Мастер — не начальник, его блок замаскирован.
    assert all(v is None for v in q["primary"]["scores"].values())
    assert q["primary"]["avg"] is None
    assert q["primary"]["comment"] is None
    assert q["primary"]["fio"] == "M-1001"  # кто оценивал — видно, баллы — нет
    assert q["combined_avg"] is None


def test_registry_questionnaire_chief_own_eval_unmasked(client, db_engine, seed):
    """Если начальник сам оценщик (primary) и сдал анкету — его баллы не маскируются."""
    from datetime import datetime

    from app.models import Evaluation, EvaluationStatus

    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    db = Session()
    asg = db.get(__import__("app.models", fromlist=["Assignment"]).Assignment, seed["asg1"].id)
    asg.primary_user_id = seed["chief"].id
    db.add(
        Evaluation(
            organization_id=seed["org"].id,
            assignment_id=asg.id,
            employee_id=seed["emp1"].id,
            evaluator_id=seed["chief"].id,
            evaluator_role=__import__("app.models", fromlist=["UserRole"]).UserRole.site_chief,
            score_quality=5,
            score_discipline=5,
            score_safety=4,
            score_skills=5,
            score_versatility=4,
            status=EvaluationStatus.submitted,
            submitted_at=datetime.now(),
        )
    )
    db.commit()
    db.close()

    r = client.get(
        f"/api/registry/questionnaire/{seed['asg1'].id}", headers=_h(seed["chief"])
    )
    assert r.status_code == 200
    q = r.json()
    # Первый блок — его собственная сданная оценка: баллы не маскируются.
    assert any(v is not None for v in q["primary"]["scores"].values())
    assert q["primary"]["avg"] is not None


def test_registry_questionnaire_pdf_download(client, seed):
    """PDF одной анкеты скачивается для admin_op с корректным media type."""
    r = client.get(
        f"/api/registry/questionnaire/{seed['asg1'].id}/pdf", headers=_h(seed["admin_op"])
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert "attachment" in r.headers.get("content-disposition", "").lower()
    # PDF-сигнатура %PDF.
    assert r.content[:4] == b"%PDF"


def test_registry_questionnaire_pdf_chief_own_site(client, seed):
    """Начальник своего участка может скачать PDF анкеты."""
    r = client.get(
        f"/api/registry/questionnaire/{seed['asg1'].id}/pdf", headers=_h(seed["chief"])
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")


def test_registry_questionnaire_pdf_foreign_site_403(client, seed):
    """Начальник чужого участка получает 403 (asg2 — другой участок)."""
    r = client.get(
        f"/api/registry/questionnaire/{seed['asg2'].id}/pdf", headers=_h(seed["chief"])
    )
    assert r.status_code == 403


def test_registry_questionnaire_pdf_404(client, seed):
    """Несуществующее закрепление → 404."""
    r = client.get("/api/registry/questionnaire/999999/pdf", headers=_h(seed["admin_op"]))
    assert r.status_code == 404