from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    admin_op = "admin_op"
    master = "master"
    foreman = "foreman"
    site_chief = "site_chief"


class EvaluationStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("organization_id", "tab_no", name="uq_user_org_tab"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    tab_no: Mapped[str] = mapped_column(String(64), index=True)
    fio: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), index=True)
    site_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    site_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="Активен")
    password_hash: Mapped[str] = mapped_column(String(255))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Employee(Base):
    """База сотрудников ОП (импорт 1С + ручной ввод Админ_ОП)."""

    __tablename__ = "employees"
    __table_args__ = (UniqueConstraint("organization_id", "tab_no", name="uq_emp_org_tab"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    tab_no: Mapped[str] = mapped_column(String(64), index=True)
    fio: Mapped[str] = mapped_column(String(255), index=True)
    territory: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department_1c: Mapped[str | None] = mapped_column(String(255), nullable=True)
    position_1c: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    experience_text: Mapped[str | None] = mapped_column(String(128), nullable=True)
    hourly_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    rate_updated_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_candidate: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class EvaluationPeriod(Base):
    __tablename__ = "evaluation_periods"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_period_org_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    code: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(128))
    starts_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Assignment(Base):
    """Плановое назначение на период: primary (+ optional dual secondary)."""

    __tablename__ = "assignments"
    __table_args__ = (
        UniqueConstraint("period_id", "employee_id", name="uq_assignment_period_emp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("evaluation_periods.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    site_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    site_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    position_fact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    worker_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    shift_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_final_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    evaluate: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    primary_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    dual_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    secondary_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    employee: Mapped[Employee] = relationship("Employee")
    primary_user: Mapped[User | None] = relationship("User", foreign_keys=[primary_user_id])
    secondary_user: Mapped[User | None] = relationship("User", foreign_keys=[secondary_user_id])


class UrgentRequest(Base):
    __tablename__ = "urgent_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    employee: Mapped[Employee] = relationship("Employee")


class UrgentEvaluator(Base):
    __tablename__ = "urgent_evaluators"
    __table_args__ = (
        UniqueConstraint("urgent_request_id", "user_id", name="uq_urgent_eval_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    urgent_request_id: Mapped[int] = mapped_column(ForeignKey("urgent_requests.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    assignment_id: Mapped[int | None] = mapped_column(
        ForeignKey("assignments.id"), nullable=True, index=True
    )
    urgent_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("urgent_requests.id"), nullable=True, index=True
    )
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    evaluator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    evaluator_role: Mapped[UserRole] = mapped_column(Enum(UserRole))
    score_quality: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_discipline: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_safety: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_skills: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_versatility: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[EvaluationStatus] = mapped_column(
        Enum(EvaluationStatus), default=EvaluationStatus.draft
    )
    client_mutation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    employee: Mapped[Employee] = relationship("Employee")
    evaluator: Mapped[User] = relationship("User")


class ProductionCoeff(Base):
    __tablename__ = "production_coeffs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("evaluation_periods.id"), index=True)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    site_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    coeff: Mapped[float] = mapped_column(Float, default=1.0)
    site_chief_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Delegation(Base):
    __tablename__ = "delegations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("evaluation_periods.id"), index=True)
    original_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    substitute_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DomainEvent(Base):
    __tablename__ = "domain_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class ListTicket(Base):
    """Тикет «ошибка в списке» от мастера/ПР."""

    __tablename__ = "list_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    assignment_id: Mapped[int | None] = mapped_column(ForeignKey("assignments.id"), nullable=True)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
