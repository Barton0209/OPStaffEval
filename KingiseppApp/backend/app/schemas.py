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


class LoginIn(BaseModel):
    tab_no: str
    password: str


class UserMe(BaseModel):
    id: int
    tab_no: str
    fio: str
    role: UserRole
    site_code: str | None
    site_name: str | None
    organization_id: int

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
    k_vyr: float | None
    final_score: float | None
    status: str
    is_urgent: bool = False
    hourly_rate: float | None = None
    rate_updated_at: date | None = None
    months_since_rate_update: int | None = None
    tariff_stale: bool = False
    employee_id: int | None = None
    assignment_id: int | None = None


class TicketIn(BaseModel):
    message: str
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


class FormalizeCandidateIn(BaseModel):
    employee_id: int
    new_tab_no: str
    hire_date: date | None = None
    position_1c: str | None = None


class KvyрIn(BaseModel):
    employee_id: int | None = None
    site_code: str | None = None
    coeff: float = Field(gt=0, le=3)
    comment: str | None = None
