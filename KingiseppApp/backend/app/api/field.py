from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.deps import get_current_user, touch_login
from app.models import (
    Assignment,
    Delegation,
    Employee,
    Evaluation,
    EvaluationPeriod,
    EvaluationStatus,
    ListTicket,
    UrgentEvaluator,
    UrgentRequest,
    User,
    UserRole,
)
from app.schemas import (
    AssignmentListItem,
    EvaluationOut,
    EvaluationScoresIn,
    LoginIn,
    TicketIn,
    TicketOut,
    TokenOut,
    UserMe,
)
from app.security import authenticate_user, create_access_token
from app.services.evaluations import (
    close_urgent_if_complete,
    link_evaluation_to_period_assignment,
)
from app.services.events import emit_event

router = APIRouter(prefix="/api/field", tags=["field"])


def _avg(ev: Evaluation) -> float | None:
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


def _active_substitute_ids(db: Session, user: User, period_id: int) -> set[int]:
    today = date.today()
    rows = (
        db.query(Delegation)
        .filter(
            Delegation.organization_id == user.organization_id,
            Delegation.period_id == period_id,
            Delegation.substitute_user_id == user.id,
            Delegation.is_active.is_(True),
            Delegation.starts_on <= today,
            Delegation.ends_on >= today,
        )
        .all()
    )
    return {d.original_user_id for d in rows}


@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    user = authenticate_user(db, body.tab_no, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Неверный табельный номер или пароль")
    if user.role not in (
        UserRole.master,
        UserRole.foreman,
        UserRole.admin_op,
        UserRole.admin,
        UserRole.site_chief,
    ):
        raise HTTPException(status_code=403, detail="Роль не допускается")
    token = create_access_token(user)
    touch_login(db, user)
    emit_event(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        entity_type="user",
        entity_id=user.id,
        action="login",
        payload={"tab_no": user.tab_no},
    )
    db.commit()
    return TokenOut(
        access_token=token,
        role=user.role,
        fio=user.fio,
        tab_no=user.tab_no,
        organization_id=user.organization_id,
    )


@router.get("/me", response_model=UserMe)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.get("/assignments", response_model=list[AssignmentListItem])
def my_assignments(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[AssignmentListItem]:
    period = (
        db.query(EvaluationPeriod)
        .filter(EvaluationPeriod.organization_id == user.organization_id, EvaluationPeriod.is_open.is_(True))
        .order_by(EvaluationPeriod.id.desc())
        .first()
    )
    if not period:
        return []

    items: list[AssignmentListItem] = []
    substitute_for = _active_substitute_ids(db, user, period.id)

    # Planned assignments
    q = (
        db.query(Assignment)
        .options(joinedload(Assignment.employee))
        .filter(
            Assignment.organization_id == user.organization_id,
            Assignment.period_id == period.id,
            Assignment.evaluate.is_(True),
        )
    )
    for asg in q.all():
        my_role = None
        if asg.primary_user_id == user.id or asg.primary_user_id in substitute_for:
            my_role = "primary"
        elif asg.dual_enabled and (
            asg.secondary_user_id == user.id or asg.secondary_user_id in substitute_for
        ):
            my_role = "secondary"
        if not my_role:
            continue
        if user.role not in (UserRole.master, UserRole.foreman, UserRole.admin_op, UserRole.admin):
            continue

        ev = (
            db.query(Evaluation)
            .filter(
                Evaluation.assignment_id == asg.id,
                Evaluation.evaluator_id == user.id,
            )
            .order_by(Evaluation.id.desc())
            .first()
        )
        emp: Employee = asg.employee
        items.append(
            AssignmentListItem(
                assignment_id=asg.id,
                employee_id=emp.id,
                tab_no=emp.tab_no,
                fio=emp.fio,
                site_code=asg.site_code,
                site_name=asg.site_name,
                position_fact=asg.position_fact,
                position_1c=emp.position_1c,
                hire_date=emp.hire_date,
                experience_text=emp.experience_text,
                last_final_score=asg.last_final_score,
                my_role=my_role,
                evaluation_id=ev.id if ev else None,
                evaluation_status=ev.status if ev else None,
                assignment_version=asg.version,
                is_urgent=False,
            )
        )

    # Urgent tasks (только открытые и ещё не сданные этим пользователем)
    urgent_ids = [
        ue.urgent_request_id
        for ue in db.query(UrgentEvaluator).filter(UrgentEvaluator.user_id == user.id).all()
    ]
    seen_keys: set[tuple[str, int]] = set()
    for it in items:
        seen_keys.add(("a" if not it.is_urgent else "u", it.employee_id if it.is_urgent else it.assignment_id))

    if urgent_ids:
        for ur in (
            db.query(UrgentRequest)
            .options(joinedload(UrgentRequest.employee))
            .filter(UrgentRequest.id.in_(urgent_ids), UrgentRequest.status == "open")
            .all()
        ):
            ev = (
                db.query(Evaluation)
                .filter(Evaluation.urgent_request_id == ur.id, Evaluation.evaluator_id == user.id)
                .order_by(Evaluation.id.desc())
                .first()
            )
            if ev and ev.status == EvaluationStatus.submitted:
                continue
            emp = ur.employee
            items.append(
                AssignmentListItem(
                    assignment_id=ev.assignment_id or 0,
                    employee_id=emp.id,
                    tab_no=emp.tab_no,
                    fio=emp.fio,
                    site_code=None,
                    site_name=None,
                    position_fact=emp.position_1c,
                    position_1c=emp.position_1c,
                    hire_date=emp.hire_date,
                    experience_text=emp.experience_text,
                    last_final_score=None,
                    my_role="urgent",
                    evaluation_id=ev.id if ev else None,
                    evaluation_status=ev.status if ev else None,
                    assignment_version=1,
                    is_urgent=True,
                    urgent_request_id=ur.id,
                )
            )
            seen_keys.add(("u", emp.id))

    # Сданные анкеты этого оценщика (в т.ч. закрытые срочные) — для блока «Готово»
    submitted_evs = (
        db.query(Evaluation)
        .options(joinedload(Evaluation.employee))
        .filter(
            Evaluation.evaluator_id == user.id,
            Evaluation.status == EvaluationStatus.submitted,
        )
        .order_by(Evaluation.submitted_at.desc(), Evaluation.id.desc())
        .limit(300)
        .all()
    )
    for ev in submitted_evs:
        emp = ev.employee
        if ev.assignment_id and ("a", ev.assignment_id) in seen_keys:
            continue
        if ev.urgent_request_id and ("u", emp.id) in seen_keys:
            continue
        # уже есть как обычное назначение в списке
        if any(
            (not i.is_urgent and i.assignment_id == ev.assignment_id)
            or (
                i.employee_id == emp.id
                and i.evaluation_status
                in (EvaluationStatus.submitted, "submitted")
            )
            for i in items
        ):
            continue
        asg = db.get(Assignment, ev.assignment_id) if ev.assignment_id else None
        items.append(
            AssignmentListItem(
                assignment_id=ev.assignment_id or 0,
                employee_id=emp.id,
                tab_no=emp.tab_no,
                fio=emp.fio,
                site_code=asg.site_code if asg else None,
                site_name=asg.site_name if asg else None,
                position_fact=(asg.position_fact if asg else None) or emp.position_1c,
                position_1c=emp.position_1c,
                hire_date=emp.hire_date,
                experience_text=emp.experience_text,
                last_final_score=asg.last_final_score if asg else None,
                my_role="urgent" if ev.urgent_request_id else "primary",
                evaluation_id=ev.id,
                evaluation_status=ev.status,
                assignment_version=asg.version if asg else 1,
                is_urgent=bool(ev.urgent_request_id),
                urgent_request_id=ev.urgent_request_id,
            )
        )
        if ev.assignment_id:
            seen_keys.add(("a", ev.assignment_id))
        else:
            seen_keys.add(("u", emp.id))

    def _is_done(it: AssignmentListItem) -> bool:
        st = it.evaluation_status
        return st == EvaluationStatus.submitted or st == "submitted"

    items.sort(key=lambda x: (not x.is_urgent or _is_done(x), _is_done(x), x.fio))
    return items


@router.get("/evaluations/{evaluation_id}", response_model=EvaluationOut)
def get_evaluation(
    evaluation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EvaluationOut:
    ev = db.get(Evaluation, evaluation_id)
    if not ev or ev.evaluator_id != user.id:
        raise HTTPException(status_code=404, detail="Анкета не найдена")
    return EvaluationOut(
        id=ev.id,
        employee_id=ev.employee_id,
        assignment_id=ev.assignment_id,
        urgent_request_id=ev.urgent_request_id,
        status=ev.status,
        score_quality=ev.score_quality,
        score_discipline=ev.score_discipline,
        score_safety=ev.score_safety,
        score_skills=ev.score_skills,
        score_versatility=ev.score_versatility,
        avg_score=_avg(ev),
        comment=ev.comment,
        submitted_at=ev.submitted_at,
    )


@router.post("/assignments/{assignment_id}/evaluation", response_model=EvaluationOut)
def save_assignment_evaluation(
    assignment_id: int,
    body: EvaluationScoresIn,
    submit: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EvaluationOut:
    asg = db.get(Assignment, assignment_id)
    if not asg or not asg.evaluate:
        raise HTTPException(status_code=404, detail="Назначение не найдено")

    allowed = asg.primary_user_id == user.id or (
        asg.dual_enabled and asg.secondary_user_id == user.id
    )
    substitute_for = _active_substitute_ids(db, user, asg.period_id)
    if asg.primary_user_id in substitute_for:
        allowed = True
    if not allowed:
        raise HTTPException(status_code=403, detail="Нет доступа к этой анкете")

    if body.assignment_version is not None and body.assignment_version != asg.version:
        return EvaluationOut(
            id=0,
            employee_id=asg.employee_id,
            assignment_id=asg.id,
            urgent_request_id=None,
            status=EvaluationStatus.draft,
            score_quality=body.score_quality,
            score_discipline=body.score_discipline,
            score_safety=body.score_safety,
            score_skills=body.score_skills,
            score_versatility=body.score_versatility,
            avg_score=None,
            comment=body.comment,
            submitted_at=None,
            conflict=True,
            conflict_message=(
                f"Назначение изменено Администрацией (версия {asg.version}). "
                "Перезаполните анкету или отмените черновик."
            ),
        )

    if body.client_mutation_id:
        existing = (
            db.query(Evaluation)
            .filter(Evaluation.client_mutation_id == body.client_mutation_id)
            .first()
        )
        if existing:
            return EvaluationOut(
                id=existing.id,
                employee_id=existing.employee_id,
                assignment_id=existing.assignment_id,
                urgent_request_id=existing.urgent_request_id,
                status=existing.status,
                score_quality=existing.score_quality,
                score_discipline=existing.score_discipline,
                score_safety=existing.score_safety,
                score_skills=existing.score_skills,
                score_versatility=existing.score_versatility,
                avg_score=_avg(existing),
                comment=existing.comment,
                submitted_at=existing.submitted_at,
            )

    ev = (
        db.query(Evaluation)
        .filter(Evaluation.assignment_id == asg.id, Evaluation.evaluator_id == user.id)
        .order_by(Evaluation.id.desc())
        .first()
    )
    if ev and ev.status == EvaluationStatus.submitted and submit:
        raise HTTPException(status_code=400, detail="Анкета уже отправлена")

    if not ev:
        ev = Evaluation(
            organization_id=user.organization_id,
            assignment_id=asg.id,
            employee_id=asg.employee_id,
            evaluator_id=user.id,
            evaluator_role=user.role,
        )
        db.add(ev)
        db.flush()
        emit_event(
            db,
            organization_id=user.organization_id,
            actor_user_id=user.id,
            entity_type="evaluation",
            entity_id=ev.id,
            action="opened",
            payload={"assignment_id": asg.id},
        )

    before = {
        "quality": ev.score_quality,
        "discipline": ev.score_discipline,
        "safety": ev.score_safety,
        "skills": ev.score_skills,
        "versatility": ev.score_versatility,
    }
    ev.score_quality = body.score_quality
    ev.score_discipline = body.score_discipline
    ev.score_safety = body.score_safety
    ev.score_skills = body.score_skills
    ev.score_versatility = body.score_versatility
    ev.comment = body.comment
    if body.client_mutation_id:
        ev.client_mutation_id = body.client_mutation_id

    for key, new_val, old_val in [
        ("score_quality", body.score_quality, before["quality"]),
        ("score_discipline", body.score_discipline, before["discipline"]),
        ("score_safety", body.score_safety, before["safety"]),
        ("score_skills", body.score_skills, before["skills"]),
        ("score_versatility", body.score_versatility, before["versatility"]),
    ]:
        if old_val != new_val:
            emit_event(
                db,
                organization_id=user.organization_id,
                actor_user_id=user.id,
                entity_type="evaluation",
                entity_id=ev.id,
                action="score_changed",
                payload={"field": key, "from": old_val, "to": new_val},
            )

    if submit:
        ev.status = EvaluationStatus.submitted
        ev.submitted_at = datetime.utcnow()
        emit_event(
            db,
            organization_id=user.organization_id,
            actor_user_id=user.id,
            entity_type="evaluation",
            entity_id=ev.id,
            action="submitted",
            payload={"avg": _avg(ev)},
        )
    else:
        ev.status = EvaluationStatus.draft

    db.commit()
    db.refresh(ev)
    return EvaluationOut(
        id=ev.id,
        employee_id=ev.employee_id,
        assignment_id=ev.assignment_id,
        urgent_request_id=ev.urgent_request_id,
        status=ev.status,
        score_quality=ev.score_quality,
        score_discipline=ev.score_discipline,
        score_safety=ev.score_safety,
        score_skills=ev.score_skills,
        score_versatility=ev.score_versatility,
        avg_score=_avg(ev),
        comment=ev.comment,
        submitted_at=ev.submitted_at,
    )


@router.post("/urgent/{urgent_id}/evaluation", response_model=EvaluationOut)
def save_urgent_evaluation(
    urgent_id: int,
    body: EvaluationScoresIn,
    submit: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EvaluationOut:
    link = (
        db.query(UrgentEvaluator)
        .filter(UrgentEvaluator.urgent_request_id == urgent_id, UrgentEvaluator.user_id == user.id)
        .first()
    )
    ur = db.get(UrgentRequest, urgent_id)
    if not link or not ur or ur.status != "open":
        raise HTTPException(status_code=404, detail="Срочная задача не найдена")

    ev = (
        db.query(Evaluation)
        .filter(Evaluation.urgent_request_id == urgent_id, Evaluation.evaluator_id == user.id)
        .order_by(Evaluation.id.desc())
        .first()
    )
    if not ev:
        ev = Evaluation(
            organization_id=user.organization_id,
            urgent_request_id=urgent_id,
            employee_id=ur.employee_id,
            evaluator_id=user.id,
            evaluator_role=user.role,
        )
        db.add(ev)
        db.flush()

    ev.score_quality = body.score_quality
    ev.score_discipline = body.score_discipline
    ev.score_safety = body.score_safety
    ev.score_skills = body.score_skills
    ev.score_versatility = body.score_versatility
    ev.comment = body.comment
    if body.client_mutation_id:
        ev.client_mutation_id = body.client_mutation_id
    if submit:
        ev.status = EvaluationStatus.submitted
        ev.submitted_at = datetime.utcnow()
        link_evaluation_to_period_assignment(db, ev)
        close_urgent_if_complete(db, ur, actor_user_id=user.id)
        emit_event(
            db,
            organization_id=user.organization_id,
            actor_user_id=user.id,
            entity_type="evaluation",
            entity_id=ev.id,
            action="urgent_submitted",
            payload={"urgent_id": urgent_id, "avg": _avg(ev), "assignment_id": ev.assignment_id},
        )
    else:
        ev.status = EvaluationStatus.draft
    db.commit()
    db.refresh(ev)
    return EvaluationOut(
        id=ev.id,
        employee_id=ev.employee_id,
        assignment_id=ev.assignment_id,
        urgent_request_id=ev.urgent_request_id,
        status=ev.status,
        score_quality=ev.score_quality,
        score_discipline=ev.score_discipline,
        score_safety=ev.score_safety,
        score_skills=ev.score_skills,
        score_versatility=ev.score_versatility,
        avg_score=_avg(ev),
        comment=ev.comment,
        submitted_at=ev.submitted_at,
    )

@router.post("/tickets", response_model=TicketOut)
def create_ticket(
    body: TicketIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ListTicket:
    if user.role not in (UserRole.master, UserRole.foreman, UserRole.admin_op, UserRole.admin):
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    if not body.message or not body.message.strip():
        raise HTTPException(status_code=400, detail="Укажите сообщение")
    ticket = ListTicket(
        organization_id=user.organization_id,
        created_by_user_id=user.id,
        assignment_id=body.assignment_id,
        employee_id=body.employee_id,
        message=body.message.strip(),
        status="new",
    )
    db.add(ticket)
    db.flush()
    emit_event(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        entity_type="list_ticket",
        entity_id=ticket.id,
        action="created",
        payload={"message": body.message},
    )
    db.commit()
    db.refresh(ticket)
    return TicketOut(
        id=ticket.id,
        message=ticket.message,
        status=ticket.status,
        assignment_id=ticket.assignment_id,
        employee_id=ticket.employee_id,
        created_by_user_id=ticket.created_by_user_id,
        created_by_fio=user.fio,
        created_by_tab_no=user.tab_no,
        admin_note=ticket.admin_note,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


@router.get("/tickets", response_model=list[TicketOut])
def my_tickets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Обращения текущего пользователя и ответы администрации."""
    rows = (
        db.query(ListTicket)
        .filter(
            ListTicket.organization_id == user.organization_id,
            ListTicket.created_by_user_id == user.id,
        )
        .order_by(ListTicket.id.desc())
        .limit(50)
        .all()
    )
    return [
        TicketOut(
            id=t.id,
            message=t.message,
            status=t.status,
            assignment_id=t.assignment_id,
            employee_id=t.employee_id,
            created_by_user_id=t.created_by_user_id,
            created_by_fio=user.fio,
            created_by_tab_no=user.tab_no,
            admin_note=t.admin_note,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in rows
    ]
