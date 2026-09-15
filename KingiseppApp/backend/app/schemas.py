from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models import EvaluationStatus, UserRole


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    fio: str
    tab_no: str
    organization_id: int
    site_code: str | None = None
    site_name: str | None = None
    must_change_password: bool = False


class LoginIn(BaseModel):
    tab_no: str
    password: str


class ChangePasswordIn(BaseModel):
    old_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)


class UserMe(BaseModel):
    id: int
    tab_no: str
    fio: str
    role: UserRole
    site_code: str | None
    site_name: str | None
    organization_id: int
    must_change_password: bool = False

    model_config = {"from_attributes": True}


class AssignmentListItem(BaseModel):
    assignment_id: int
    employee_id: int
    tab_no: str
    fio: str
    site_code: str | None
    site_name: str | None
    position_fact: str | None
    position_1c: str | None
    hire_date: date | None
    experience_text: str | None
    last_final_score: float | None
    my_role: str
    evaluation_id: int | None
    evaluation_status: EvaluationStatus | None
    assignment_version: int
    is_urgent: bool = False
    urgent_request_id: int | None = None
    # ЧТС и сводная оценка (для ЛК начальника участка)
    hourly_rate: float | None = None
    rate_updated_at: date | None = None
    rate_last_raised: date | None = None  # дата последнего поднятия ЧТС
    is_rate_expired: bool = False  # >= 180 дней без поднятия ЧТС
    tariff_min: float | None = None  # мин по тарифной сетке (должность + гражданство)
    tariff_max: float | None = None
    combined_score: float | None = None  # общая (1-й + 2-й), когда обе анкеты сданы
    peer_submitted: bool = False  # второй оценщик уже сдал


class EvaluationScoresIn(BaseModel):
    score_quality: int = Field(ge=1, le=5)
    score_discipline: int = Field(ge=1, le=5)
    score_safety: int = Field(ge=1, le=5)
    score_skills: int = Field(ge=1, le=5)
    score_versatility: int = Field(ge=1, le=5)
    comment: str | None = None
    client_mutation_id: str | None = None
    assignment_version: int | None = None


class EvaluationOut(BaseModel):
    id: int
    employee_id: int
    assignment_id: int | None
    urgent_request_id: int | None
    status: EvaluationStatus
    score_quality: int | None
    score_discipline: int | None
    score_safety: int | None
    score_skills: int | None
    score_versatility: int | None
    avg_score: float | None
    comment: str | None
    submitted_at: datetime | None
    conflict: bool = False
    conflict_message: str | None = None
    conflict_diff: dict | None = None

    model_config = {"from_attributes": True}


class ImportResult(BaseModel):
    source: str
    added: int
    updated: int
    skipped: int
    errors: list[str]


class DashboardOut(BaseModel):
    organization: str
    period_code: str
    total_assignments: int
    evaluate_yes: int
    with_primary: int
    awaiting_primary: int
    candidates: int
    submitted_evaluations: int
    dual_enabled: int
    open_urgent: int
    open_tickets: int = 0
    escalations: int = 0


class RegistryRow(BaseModel):
    tab_no: str
    fio: str
    position: str | None
    site_name: str | None
    primary_fio: str | None
    primary_avg: float | None
    secondary_fio: str | None
    secondary_avg: float | None
    combined_avg: float | None = None
    k_vyr: float | None
    final_score: float | None
    status: str
    is_urgent: bool = False
    hourly_rate: float | None = None
    rate_updated_at: date | None = None
    rate_last_raised: date | None = None
    months_since_rate_update: int | None = None
    tariff_stale: bool = False
    is_rate_expired: bool = False  # >= 180 дней без поднятия ЧТС (красная подсветка)
    tariff_min: float | None = None
    tariff_max: float | None = None
    citizenship: str | None = None
    employee_id: int | None = None
    assignment_id: int | None = None
    # Испытательный срок сотрудника.
    probation_end_date: date | None = None
    probation_active: bool = False


class TicketIn(BaseModel):
    message: str = Field(max_length=5000)
    assignment_id: int | None = None
    employee_id: int | None = None


class TicketOut(BaseModel):
    id: int
    message: str
    status: str
    assignment_id: int | None
    employee_id: int | None
    created_by_user_id: int
    created_by_fio: str | None = None
    created_by_tab_no: str | None = None
    admin_note: str | None
    created_at: datetime | None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class DelegationIn(BaseModel):
    original_user_id: int
    substitute_user_id: int
    starts_on: date
    ends_on: date
    reason: str | None = None


class EmployeeCreateIn(BaseModel):
    tab_no: str
    fio: str
    position_1c: str | None = None
    department_1c: str | None = None
    hire_date: date | None = None
    is_candidate: bool = False


class EmployeePatchIn(BaseModel):
    """Правка сотрудника: ЧТС и дата последнего поднятия."""

    hourly_rate: float | None = Field(default=None, ge=0, le=10_000_000)
    rate_last_raised: date | None = None


class EconomistRateUpdateIn(BaseModel):
    """Изменение ЧТС сотрудника экономистом (с датой и комментарием)."""

    tab_no: str = Field(min_length=1, max_length=64)
    changed_at: date
    new_rate: float = Field(gt=0, le=10_000_000)
    comment: str | None = Field(default=None, max_length=500)


class RateHistoryOut(BaseModel):
    """Запись истории изменения ЧТС."""

    id: int
    employee_id: int
    old_rate: float | None
    new_rate: float
    changed_at: date
    comment: str | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class TariffGridOut(BaseModel):
    """Строка тарифной сетки (должность + гражданство + мин/макс ЧТС)."""

    position: str
    citizenship: str
    min_rate: float
    max_rate: float


class FormalizeCandidateIn(BaseModel):
    employee_id: int
    new_tab_no: str
    hire_date: date | None = None
    position_1c: str | None = None


class KvyrIn(BaseModel):
    employee_id: int | None = None
    site_code: str | None = None
    coeff: float = Field(gt=0, le=3)
    comment: str | None = None


class UserPatchIn(BaseModel):
    """Правка пользователя из «Настроек»: роль, участок, статус, пароль."""

    role: UserRole | None = None
    site_code: str | None = None
    site_name: str | None = None
    status: str | None = Field(default=None, min_length=1, max_length=32)
    password: str | None = Field(default=None, min_length=8, max_length=72)


class UserCreateIn(BaseModel):
    """Новый пользователь из «Настроек»."""

    tab_no: str = Field(min_length=1, max_length=64)
    fio: str = Field(min_length=1, max_length=255)
    role: UserRole
    site_code: str | None = None
    site_name: str | None = None
    status: str = Field(default="Активен", min_length=1, max_length=32)
    password: str = Field(min_length=8, max_length=72)


class SecondAssignIn(BaseModel):
    """Назначение/снятие 2-го оценщика (начальника участка)."""

    assignment_ids: list[int] = Field(min_length=1)
    secondary_user_id: int | None = None  # None = снять 2-го оценщика


# ==================== Group_of_Users ====================

class GroupOfUsersCreate(BaseModel):
    """Создание группы пользователей."""
    territory_name: str = Field(min_length=1, max_length=255)
    department_name: str | None = Field(default=None, max_length=255)
    group_name: str = Field(min_length=1, max_length=128)
    permission: str | None = Field(default=None, max_length=255)


class GroupOfUsersUpdate(BaseModel):
    """Обновление группы пользователей."""
    territory_name: str | None = Field(default=None, max_length=255)
    department_name: str | None = Field(default=None, max_length=255)
    group_name: str | None = Field(default=None, max_length=128)
    permission: str | None = Field(default=None, max_length=255)


class GroupOfUsersOut(BaseModel):
    """Вывод группы пользователей."""
    id: int
    territory_id: int | None
    territory_name: str | None
    department_id: int | None
    department_name: str | None
    group_name: str | None
    permission: str | None

    model_config = {"from_attributes": True}
