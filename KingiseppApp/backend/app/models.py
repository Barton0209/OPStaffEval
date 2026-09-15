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
    Index,
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
    management_op = "management_op"  # Руководство ОП
    economist = "economist"
    master = "master"
    foreman = "foreman"
    site_chief = "site_chief"
    cok_okit = "cok_okit"  # ЦОК_ОКиТ — главный администратор по всем площадкам
    cok_adapt = "cok_adapt"  # ЦОК_Адаптация
    cok_otiz = "cok_otiz"  # ЦОК_ОТиЗ


class UserStatus(str, enum.Enum):
    active = "Активен"
    disabled = "Отключен"


class TicketStatus(str, enum.Enum):
    new = "new"
    in_progress = "in_progress"
    done = "done"


class UrgentStatus(str, enum.Enum):
    open = "open"
    closed = "closed"


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
    status: Mapped[UserStatus] = mapped_column(String(32), default=UserStatus.active)
    password_hash: Mapped[str] = mapped_column(String(255))
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    # Версия токена: инкрементируется при смене пароля — старые JWT становятся недействительными.
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    # last_login_at хранит aware-datetime (UTC) для корректной работы escalation detection.
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
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
    # Гражданство (из УД-списка) — для сопоставления с тарифной сеткой.
    citizenship: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hourly_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    rate_updated_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Дата последнего поднятия ЧТС (источник: УД-список .xlsb / ручное изменение).
    rate_last_raised: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Разряд (из УД-списка/вручную) и дата окончания испытательного срока.
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    probation_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_candidate: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class RateHistory(Base):
    """История изменения ЧТС сотрудника (экономест ведёт ежемесячно)."""

    __tablename__ = "rate_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    old_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    new_rate: Mapped[float] = mapped_column(Float)
    changed_at: Mapped[date] = mapped_column(Date, index=True)
    changed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    employee: Mapped[Employee] = relationship("Employee")


class TariffGrid(Base):
    """Тарифная сетка: мин/макс ЧТС по должности и гражданству (импорт из Сводная_тарифная_сетка.xlsx)."""

    __tablename__ = "tariff_grids"
    __table_args__ = (
        UniqueConstraint("position", "citizenship", name="uq_tariff_position_citizenship"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position: Mapped[str] = mapped_column(String(255), index=True)
    citizenship: Mapped[str] = mapped_column(String(64), index=True)
    min_rate: Mapped[float] = mapped_column(Float, default=0.0)
    max_rate: Mapped[float] = mapped_column(Float, default=0.0)
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
    status: Mapped[UrgentStatus] = mapped_column(String(32), default=UrgentStatus.open)
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
    __table_args__ = (
        # Composite index для самого частого паттерна запроса:
        # WHERE assignment_id = ? AND evaluator_id = ? AND status = ?
        Index(
            "ix_evaluations_asg_eval_status", "assignment_id", "evaluator_id", "status"
        ),
    )

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
        Enum(EvaluationStatus), default=EvaluationStatus.draft, index=True
    )
    client_mutation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
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


class PasswordSetupCode(Base):
    """Hashed, expiring, single-use proof for first login/password reset."""

    __tablename__ = "password_setup_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ListTicket(Base):
    """Тикет «ошибка в списке» от мастера/ПР."""

    __tablename__ = "list_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    assignment_id: Mapped[int | None] = mapped_column(ForeignKey("assignments.id"), nullable=True)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[TicketStatus] = mapped_column(String(32), default=TicketStatus.new, index=True)
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# ==================== Новые модели для «Контроль» ====================


class Territory(Base):
    """Площадка / территория (ОП Горно-Алтайск, ОП Кингисепп-2.ЕвроХим и т.д.)."""

    __tablename__ = "territories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    code: Mapped[str] = mapped_column(String(128), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Department(Base):
    """Отдел / роль (Линейный ИТР, Администрация ОП, Экономисты ОП и т.д.)."""

    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(128))
    system_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class GroupOfUsers(Base):
    """Связка Territory → Role → Group_of_Users (из листа Group_of_Users)."""

    __tablename__ = "groups_of_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    territory_id: Mapped[int | None] = mapped_column(ForeignKey("territories.id"), nullable=True)
    territory_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    department_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    group_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    permission: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UserTerritoryMapping(Base):
    """Связка пользователя с Territory/Department (из листа Users)."""

    __tablename__ = "user_territory_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    territory_id: Mapped[int | None] = mapped_column(ForeignKey("territories.id"), nullable=True)
    territory_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    department_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    group_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    actual_position: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ImportLog(Base):
    """Журнал загрузок файлов — отображается во вкладке «Настройка»."""

    __tablename__ = "import_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    block_name: Mapped[str] = mapped_column(String(128))  # «База сотрудников», «Ежедневный учет» и т.д.
    slot_name: Mapped[str | None] = mapped_column(String(128), nullable=True)  # для реестров: «2024 1 полугодие»
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    uploaded_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    added: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    archived: Mapped[int] = mapped_column(Integer, default=0)
    errors_count: Mapped[int] = mapped_column(Integer, default=0)
    error_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)


class FiredEmployee(Base):
    """Архив уволенных сотрудников (soft-delete)."""

    __tablename__ = "fired_employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    original_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    tab_no: Mapped[str] = mapped_column(String(64), index=True)
    fio: Mapped[str] = mapped_column(String(255))
    territory: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department_1c: Mapped[str | None] = mapped_column(String(255), nullable=True)
    position_1c: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    citizenship: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    fire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hourly_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    fire_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    fired_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    fired_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    original_employee: Mapped[Employee | None] = relationship("Employee")


class Transfer(Base):
    """Перевод сотрудника на другое ОП/площадку."""

    __tablename__ = "transfers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    from_territory: Mapped[str | None] = mapped_column(String(255), nullable=True)
    to_territory: Mapped[str | None] = mapped_column(String(255), nullable=True)
    to_site_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    to_site_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    transfer_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="planned")
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RegistryImport(Base):
    """Импортированные реестры оценок (12 критериев) по периодам."""

    __tablename__ = "registry_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    period_year: Mapped[int] = mapped_column(Integer)  # 2024, 2025, 2026
    period_half: Mapped[int] = mapped_column(Integer)  # 1 или 2
    file_name: Mapped[str] = mapped_column(String(255))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    uploaded_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    added: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    errors_count: Mapped[int] = mapped_column(Integer, default=0)
    error_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)


class RegistryScore(Base):
    """Оценка из реестра (12 критериев × 2 оценщика)."""

    __tablename__ = "registry_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    registry_import_id: Mapped[int] = mapped_column(ForeignKey("registry_imports.id"), index=True)
    tab_no: Mapped[str] = mapped_column(String(64), index=True)
    fio: Mapped[str] = mapped_column(String(255))
    territory: Mapped[str | None] = mapped_column(String(255), nullable=True)
    position: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    master_fio: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # 12 критериев первой оценки
    c1_first: Mapped[int | None] = mapped_column(Integer, nullable=True)
    c2_first: Mapped[int | None] = mapped_column(Integer, nullable=True)
    c3_first: Mapped[int | None] = mapped_column(Integer, nullable=True)
    c4_first: Mapped[int | None] = mapped_column(Integer, nullable=True)
    c5_first: Mapped[int | None] = mapped_column(Integer, nullable=True)
    c6_first: Mapped[int | None] = mapped_column(Integer, nullable=True)
    c7_first: Mapped[int | None] = mapped_column(Integer, nullable=True)
    c8_first: Mapped[int | None] = mapped_column(Integer, nullable=True)
    c9_first: Mapped[int | None] = mapped_column(Integer, nullable=True)
    c10_first: Mapped[int | None] = mapped_column(Integer, nullable=True)
    c11_first: Mapped[int | None] = mapped_column(Integer, nullable=True)
    c12_first: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_first: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 12 критериев второй оценки
    c1_second: Mapped[int | None] = mapped_column(Integer, nullable=True)
    c2_second: Mapped[int | None] = mapped_column(Integer, nullable=True)
    c3_second: Mapped[int | None] = mapped_column(Integer, nullable=True)
    c4_second: Mapped[int | None] = mapped_column(Integer, nullable=True)
    c5_second: Mapped[int | None] = mapped_column(Integer, nullable=True)
    c6_second: Mapped[int | None] = mapped_column(Integer, nullable=True)
    c7_second: Mapped[int | None] = mapped_column(Integer, nullable=True)
    c8_second: Mapped[int | None] = mapped_column(Integer, nullable=True)
    c9_second: Mapped[int | None] = mapped_column(Integer, nullable=True)
    c10_second: Mapped[int | None] = mapped_column(Integer, nullable=True)
    c11_second: Mapped[int | None] = mapped_column(Integer, nullable=True)
    c12_second: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_second: Mapped[float | None] = mapped_column(Float, nullable=True)

    prod_coeff: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)
