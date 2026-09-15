import {
    request,
    type SaveEvaluationResult,
    type SessionUser,
    type Ticket,
} from "./shared";

// Временно: sessionStorage вместо localStorage (совместимо с shared.ts)
const storage = typeof window !== "undefined" ? window.sessionStorage : null;

export type AssignmentItem = {
    assignment_id: number;
    employee_id: number;
    tab_no: string;
    fio: string;
    site_code: string | null;
    site_name: string | null;
    position_fact: string | null;
    position_1c: string | null;
    hire_date: string | null;
    experience_text: string | null;
    last_final_score: number | null;
    my_role: string;
    evaluation_id: number | null;
    evaluation_status: string | null;
    assignment_version: number;
    is_urgent: boolean;
    urgent_request_id: number | null;
    hourly_rate: number | null;
    rate_updated_at: string | null;
    rate_last_raised: string | null;
    is_rate_expired: boolean;
    tariff_min: number | null;
    tariff_max: number | null;
    combined_score: number | null;
    peer_submitted: boolean;
};

export type SiteOverview = {
    site_name: string | null;
    period_code: string;
    period_starts_on: string | null;
    evaluation_started_on: string | null;
    tariff_min: number | null;
    tariff_max: number | null;
    total: number;
    masters: {
        user_id: number;
        fio: string;
        tab_no: string;
        role: string;
        total: number;
        submitted: number;
        remaining: number;
    }[];
    warning?: string | null;
};

export type QuestionnaireEvaluator = {
    evaluator_id?: number | null;
    fio: string | null;
    tab_no: string | null;
    role: string | null;
    role_ru: string;
    status: string;
    scores: Record<string, number | null>;
    avg: number | null;
    comment: string | null;
    submitted_at: string | null;
};

export type Questionnaire = {
    assignment_id: number;
    period_code: string;
    employee: {
        tab_no: string;
        fio: string;
        position: string | null;
        site_name: string | null;
        hire_date: string | null;
        experience_text: string | null;
        hourly_rate: number | null;
        rate_updated_at: string | null;
        rate_last_raised: string | null;
        citizenship: string | null;
        is_rate_expired: boolean;
        tariff_min: number | null;
        tariff_max: number | null;
        probation_end_date?: string | null;
        probation_active?: boolean;
    };
    criteria: { key: string; title: string }[];
    primary: QuestionnaireEvaluator | null;
    secondary: QuestionnaireEvaluator | null;
    dual_enabled: boolean;
    combined_avg: number | null;
    k_vyr: number;
    final_score: number | null;
    status: string;
};

export async function apiLogin(tab_no: string, password: string): Promise<SessionUser> {
    const data = await request<SessionUser & { access_token: string }>("/api/field/auth/login", {
        method: "POST",
        body: JSON.stringify({ tab_no, password }),
    });
    storage?.setItem("kingisepp_token", data.access_token);
    storage?.setItem("kingisepp_user", JSON.stringify(data));
    return data;
}

export async function apiMe(): Promise<SessionUser> {
    return request<SessionUser>("/api/field/me");
}

export async function apiChangePassword(oldPassword: string, newPassword: string): Promise<SessionUser> {
    const data = await request<SessionUser & { access_token: string }>("/api/field/me/password", {
        method: "POST",
        body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
    });
    storage?.setItem("kingisepp_token", data.access_token);
    let user: SessionUser = { ...data };
    const stored = storage?.getItem("kingisepp_user");
    if (stored) {
        try {
            user = { ...JSON.parse(stored), ...data };
        } catch {
            /* ignore */
        }
    }
    storage?.setItem("kingisepp_user", JSON.stringify(user));
    return user;
}

export async function apiMyAssignments(): Promise<AssignmentItem[]> {
    return request<AssignmentItem[]>("/api/field/assignments");
}

export async function apiSaveEvaluation(
    kind: "assignment" | "urgent",
    id: number,
    body: Record<string, unknown>,
    submit: boolean,
): Promise<SaveEvaluationResult> {
    const path =
        kind === "assignment"
            ? `/api/field/assignments/${id}/evaluation?submit=${submit}`
            : `/api/field/urgent/${id}/evaluation?submit=${submit}`;
    return request<SaveEvaluationResult>(path, { method: "POST", body: JSON.stringify(body) });
}

export async function apiDiscardDraft(assignmentId: number): Promise<{ ok: boolean }> {
    return request(`/api/field/assignments/${assignmentId}/discard-draft`, { method: "POST" });
}

export async function apiGetEvaluation(evaluationId: number) {
    return request<{
        id: number;
        status: string;
        score_quality: number | null;
        score_discipline: number | null;
        score_safety: number | null;
        score_skills: number | null;
        score_versatility: number | null;
        comment: string | null;
        avg_score: number | null;
    }>(`/api/field/evaluations/${evaluationId}`);
}

export async function apiCreateTicket(body: {
    message: string;
    assignment_id?: number | null;
    employee_id?: number | null;
}) {
    return request<Ticket>("/api/field/tickets", { method: "POST", body: JSON.stringify(body) });
}

export async function apiMyTickets() {
    return request<Ticket[]>("/api/field/tickets");
}

export async function apiSiteOverview() {
    return request<SiteOverview>("/api/field/site-overview");
}