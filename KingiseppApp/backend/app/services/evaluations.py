"""Общая логика оценок: срочные заявки ↔ назначения ↔ реестр."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Assignment,
    Evaluation,
    EvaluationStatus,
    UrgentEvaluator,
    UrgentRequest,
)
from app.services.events import emit_event
from app.services.imports import ensure_org_and_period

settings = get_settings()


def avg_scores(ev: Evaluation | None) -> float | None:
    if not ev:
        return None
    scores = [
        ev.score_quality,
        ev.score_discipline,
        ev.score_safety,
        ev.score_skills,
        ev.score_versatility,
    ]
    if any(s is None for s in scores):
        return None
    return round(sum(scores) / 5, 2)  # type: ignore[arg-type]


def link_evaluation_to_period_assignment(db: Session, ev: Evaluation) -> Assignment | None:
    """Привязать оценку (в т.ч. срочную) к evaluate=yes назначению текущего периода."""
    if ev.assignment_id:
        return db.get(Assignment, ev.assignment_id)
    _, period = ensure_org_and_period(db, settings.org_code, settings.org_name)
    asg = (
        db.query(Assignment)
        .filter(
            Assignment.period_id == period.id,
            Assignment.employee_id == ev.employee_id,
            Assignment.evaluate.is_(True),
        )
        .order_by(Assignment.id.desc())
        .first()
    )
    if asg:
        ev.assignment_id = asg.id
    return asg


def close_urgent_if_complete(
    db: Session,
    ur: UrgentRequest,
    *,
    actor_user_id: int | None = None,
) -> bool:
    """Закрыть срочную заявку, когда все назначенные оценщики отправили анкету."""
    evaluator_ids = [
        ue.user_id
        for ue in db.query(UrgentEvaluator).filter(UrgentEvaluator.urgent_request_id == ur.id).all()
    ]
    if not evaluator_ids:
        return False
    for uid in evaluator_ids:
        done = (
            db.query(Evaluation)
            .filter(
                Evaluation.urgent_request_id == ur.id,
                Evaluation.evaluator_id == uid,
                Evaluation.status == EvaluationStatus.submitted,
            )
            .first()
        )
        if not done:
            return False
    if ur.status != "closed":
        ur.status = "closed"
        ur.closed_at = datetime.utcnow()
        emit_event(
            db,
            organization_id=ur.organization_id,
            actor_user_id=actor_user_id,
            entity_type="urgent_request",
            entity_id=ur.id,
            action="closed",
            payload={"reason": "all_evaluators_submitted"},
        )
    return True


def find_submitted_for_assignment(
    db: Session,
    assignment_id: int,
    evaluator_id: int | None = None,
) -> Evaluation | None:
    if evaluator_id:
        ev = (
            db.query(Evaluation)
            .filter(
                Evaluation.assignment_id == assignment_id,
                Evaluation.evaluator_id == evaluator_id,
                Evaluation.status == EvaluationStatus.submitted,
            )
            .order_by(Evaluation.id.desc())
            .first()
        )
        if ev:
            return ev
    return (
        db.query(Evaluation)
        .filter(
            Evaluation.assignment_id == assignment_id,
            Evaluation.status == EvaluationStatus.submitted,
        )
        .order_by(Evaluation.id.desc())
        .first()
    )


def assignment_registry_status(
    db: Session, asg: Assignment
) -> tuple[Evaluation | None, Evaluation | None, float | None, float | None, str]:
    """Вернуть (primary_ev, secondary_ev, p_avg, s_avg, status) как в реестре."""
    primary_ev = None
    if asg.primary_user_id:
        primary_ev = (
            db.query(Evaluation)
            .filter(
                Evaluation.assignment_id == asg.id,
                Evaluation.evaluator_id == asg.primary_user_id,
                Evaluation.status == EvaluationStatus.submitted,
            )
            .order_by(Evaluation.id.desc())
            .first()
        )
    if not primary_ev:
        # срочная / замещение: любая отправленная анкета по этому назначению
        q = db.query(Evaluation).filter(
            Evaluation.assignment_id == asg.id,
            Evaluation.status == EvaluationStatus.submitted,
        )
        if asg.dual_enabled and asg.secondary_user_id:
            q = q.filter(Evaluation.evaluator_id != asg.secondary_user_id)
        primary_ev = q.order_by(Evaluation.id.desc()).first()

    secondary_ev = None
    if asg.dual_enabled and asg.secondary_user_id:
        secondary_ev = (
            db.query(Evaluation)
            .filter(
                Evaluation.assignment_id == asg.id,
                Evaluation.evaluator_id == asg.secondary_user_id,
                Evaluation.status == EvaluationStatus.submitted,
            )
            .order_by(Evaluation.id.desc())
            .first()
        )

    p_avg = avg_scores(primary_ev)
    s_avg = avg_scores(secondary_ev)
    status = "ожидает"
    if p_avg is not None and (not asg.dual_enabled or s_avg is not None):
        status = "закрыто"
    elif p_avg is not None:
        status = "частично"
    return primary_ev, secondary_ev, p_avg, s_avg, status


def count_closed_assignments(db: Session, period_id: int) -> int:
    assignments = (
        db.query(Assignment)
        .filter(Assignment.period_id == period_id, Assignment.evaluate.is_(True))
        .all()
    )
    return sum(1 for asg in assignments if assignment_registry_status(db, asg)[4] == "закрыто")


def repair_completed_urgents(db: Session) -> int:
    """Закрыть уже отвеченные срочные и привязать оценки к назначениям (разовый ремонт данных)."""
    fixed = 0
    open_rows = db.query(UrgentRequest).filter(UrgentRequest.status == "open").all()
    for ur in open_rows:
        evals = (
            db.query(Evaluation)
            .filter(
                Evaluation.urgent_request_id == ur.id,
                Evaluation.status == EvaluationStatus.submitted,
            )
            .all()
        )
        for ev in evals:
            link_evaluation_to_period_assignment(db, ev)
        if close_urgent_if_complete(db, ur, actor_user_id=None):
            fixed += 1
    if fixed:
        db.commit()
    return fixed
