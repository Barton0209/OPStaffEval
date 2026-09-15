"""Общая логика оценок: срочные заявки ↔ назначения ↔ реестр, эскалации."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Assignment,
    Delegation,
    Evaluation,
    EvaluationStatus,
    UrgentEvaluator,
    UrgentRequest,
    UrgentStatus,
    User,
)
from app.services.events import emit_event
from app.services.imports import ensure_org_and_period, nf

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


def covering_evaluator_ids(
    db: Session,
    *,
    organization_id: int,
    period_id: int,
    original_user_id: int | None,
) -> set[int]:
    """Оригинальный оценщик + все, кто замещал его в периоде (в т.ч. уже завершившие)."""
    if not original_user_id:
        return set()
    ids: set[int] = {original_user_id}
    for d in (
        db.query(Delegation)
        .filter(
            Delegation.organization_id == organization_id,
            Delegation.period_id == period_id,
            Delegation.original_user_id == original_user_id,
        )
        .all()
    ):
        ids.add(d.substitute_user_id)
    return ids


def covering_map(
    db: Session,
    *,
    organization_id: int,
    period_id: int,
) -> dict[int, set[int]]:
    """original_user_id -> множество заместителей периода (ОДИН запрос на период).

    Используется вместо covering_evaluator_ids в циклах для устранения N+1.
    """
    result: dict[int, set[int]] = {}
    rows = (
        db.query(Delegation)
        .filter(
            Delegation.organization_id == organization_id,
            Delegation.period_id == period_id,
        )
        .all()
    )
    for d in rows:
        result.setdefault(d.original_user_id, set()).add(d.substitute_user_id)
    return result


def site_matches(user_site: str | None, assignment_site: str | None) -> bool:
    """Сравнение участков (нормализация как в импорте)."""
    us = nf(user_site)
    if not us:
        return False
    return us == nf(assignment_site)


def filter_assignments_for_chief(assignments: list, user) -> list:
    """Для начальника участка — только его site_name; без участка — пусто."""
    from app.models import UserRole

    if getattr(user, "role", None) != UserRole.site_chief:
        return assignments
    if not nf(getattr(user, "site_name", None)):
        return []
    return [a for a in assignments if site_matches(user.site_name, a.site_name)]


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
    if ur.status != UrgentStatus.closed:
        ur.status = UrgentStatus.closed
        ur.closed_at = datetime.now(timezone.utc).replace(tzinfo=None)
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


def _latest_submitted(
    db: Session, assignment_id: int, evaluator_ids: set[int]
) -> Evaluation | None:
    if not evaluator_ids:
        return None
    return (
        db.query(Evaluation)
        .filter(
            Evaluation.assignment_id == assignment_id,
            Evaluation.evaluator_id.in_(evaluator_ids),
            Evaluation.status == EvaluationStatus.submitted,
        )
        .order_by(Evaluation.id.desc())
        .first()
    )


def assignment_registry_status(
    db: Session, asg: Assignment
) -> tuple[Evaluation | None, Evaluation | None, float | None, float | None, str]:
    """Вернуть (primary_ev, secondary_ev, p_avg, s_avg, status) как в реестре.

    Учитывает заместителей: анкета от substitute_user_id засчитывается за
    original (1-го или 2-го оценщика).
    """
    primary_ids = covering_evaluator_ids(
        db,
        organization_id=asg.organization_id,
        period_id=asg.period_id,
        original_user_id=asg.primary_user_id,
    )
    secondary_ids: set[int] = set()
    if asg.dual_enabled and asg.secondary_user_id:
        secondary_ids = covering_evaluator_ids(
            db,
            organization_id=asg.organization_id,
            period_id=asg.period_id,
            original_user_id=asg.secondary_user_id,
        )

    primary_ev = _latest_submitted(db, asg.id, primary_ids)
    if not primary_ev:
        # срочная / иной оценщик: любая сданная, кроме роли 2-го
        q = db.query(Evaluation).filter(
            Evaluation.assignment_id == asg.id,
            Evaluation.status == EvaluationStatus.submitted,
        )
        if secondary_ids:
            q = q.filter(~Evaluation.evaluator_id.in_(secondary_ids))
        primary_ev = q.order_by(Evaluation.id.desc()).first()

    secondary_ev = _latest_submitted(db, asg.id, secondary_ids)

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


def escalation_report(
    db: Session,
    *,
    organization_id: int,
    period_id: int,
) -> list[dict]:
    """Эскалации: оценивающие с просроченными заданиями (не входили 3+ дня).

    Единая реализация для дашборда, API и планировщика (устраняет дублирование).
    """
    threshold = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=3)
    primaries = (
        db.query(Assignment.primary_user_id)
        .filter(
            Assignment.organization_id == organization_id,
            Assignment.period_id == period_id,
            Assignment.evaluate.is_(True),
            Assignment.primary_user_id.is_not(None),
        )
        .distinct()
        .all()
    )
    out: list[dict] = []
    for (uid,) in primaries:
        user = db.get(User, uid)
        if not user or user.organization_id != organization_id:
            continue
        pending = (
            db.query(Assignment)
            .filter(
                Assignment.period_id == period_id,
                Assignment.primary_user_id == uid,
                Assignment.evaluate.is_(True),
            )
            .count()
        )
        submitted = (
            db.query(Evaluation)
            .join(Assignment, Assignment.id == Evaluation.assignment_id)
            .filter(
                Evaluation.evaluator_id == uid,
                Evaluation.status == EvaluationStatus.submitted,
                Evaluation.assignment_id.is_not(None),
                Assignment.period_id == period_id,
            )
            .count()
        )
        if pending > submitted and (user.last_login_at is None or user.last_login_at < threshold):
            out.append(
                {
                    "user_id": user.id,
                    "tab_no": user.tab_no,
                    "fio": user.fio,
                    "last_login_at": user.last_login_at,
                    "pending_assignments": pending,
                    "submitted": submitted,
                }
            )
    return out


def escalation_count(
    db: Session,
    *,
    organization_id: int,
    period_id: int,
) -> int:
    return len(escalation_report(db, organization_id=organization_id, period_id=period_id))


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
