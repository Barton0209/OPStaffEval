import { apiUrl, getToken, request, type Ticket } from "./shared";

export type Dashboard = {
    organization: string;
    period_code: string;
    total_assignments: number;
    evaluate_yes: number;
    with_primary: number;
    awaiting_primary: number;
    candidates: number;
    submitted_evaluations: number;
    dual_enabled: number;
    open_urgent: number;
    open_tickets: number;
    escalations: number;
};

export type AdminUser = {
    id: number;
    tab_no: string;
    fio: string;
    role: string;
    site_code: string | null;
    site_name: string | null;
    status: string;
    last_login_at: string | null;
};

export type SecondEvalRow = {
    assignment_id: number;
    employee_id: number;
    tab_no: string;
    fio: string;
    is_candidate: boolean;
    site_code: string | null;
    site_name: string | null;
    evaluate: boolean;
    primary_user_id: number | null;
    primary_fio: string | null;
    primary_eval_status: "none" | "draft" | "submitted";
    dual_enabled: boolean;
    secondary_user_id: number | null;
    secondary_fio: string | null;
    secondary_eval_status: "none" | "draft" | "submitted";
    version: number;
};

export type AdminEmployee = {
    id: number;
    tab_no: string;
    fio: string;
    position_1c: string | null;
    is_candidate: boolean;
    hire_date: string | null;
    citizenship?: string | null;
    hourly_rate?: number | null;
    rate_updated_at?: string | null;
    rate_last_raised?: string | null;
    is_rate_expired?: boolean;
    tariff_min?: number | null;
    tariff_max?: number | null;
};

export type TariffGridRow = {
    position: string;
    citizenship: string;
    min_rate: number;
    max_rate: number;
};

export type AdminAssignment = {
    assignment_id: number;
    employee_id: number;
    tab_no: string;
    fio: string;
    is_candidate: boolean;
    site_code: string | null;
    site_name: string | null;
    position_fact?: string | null;
    evaluate: boolean;
    primary_fio: string | null;
    primary_tab: string | null;
    primary_role?: string | null;
    primary_user_id: number | null;
    dual_enabled: boolean;
    secondary_user_id: number | null;
    worker_status: string | null;
    version: number;
};

export async function apiDashboard() {
    return request<Dashboard>("/api/admin/dashboard");
}

export async function apiImportAll() {
    return request<{ source: string; added: number; updated: number; skipped: number; errors: string[] }[]>(
        "/api/admin/import/all",
        { method: "POST" },
        { timeoutMs: 300000 },
    );
}

export async function apiImportUpload(files: {
    base?: File | null;
    users?: File | null;
    carnet?: File | null;
    ud?: File | null;
}) {
    const form = new FormData();
    if (files.base) form.append("base_file", files.base);
    if (files.users) form.append("users_file", files.users);
    if (files.carnet) form.append("carnet_file", files.carnet);
    if (files.ud) form.append("ud_file", files.ud);
    const headers = new Headers();
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const res = await fetch(apiUrl("/api/admin/import/upload"), { method: "POST", headers, body: form });
    if (!res.ok) {
        let detail = res.statusText;
        try {
            const body = await res.json();
            detail = body.detail || JSON.stringify(body);
        } catch {
            /* ignore */
        }
        throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return res.json() as Promise<
        { source: string; added: number; updated: number; skipped: number; errors: string[] }[]
    >;
}

export async function apiAdminAssignments(params?: { q?: string; awaiting?: boolean }) {
    const qs = new URLSearchParams();
    if (params?.q) qs.set("q", params.q);
    if (params?.awaiting) qs.set("awaiting_primary", "true");
    const suffix = qs.toString() ? `?${qs}` : "";
    return request<AdminAssignment[]>(`/api/admin/assignments${suffix}`);
}

export async function apiPatchAssignment(
    id: number,
    body: {
        primary_user_id?: number | null;
        evaluate?: boolean | null;
        dual_enabled?: boolean | null;
        secondary_user_id?: number | null;
    },
) {
    return request(`/api/admin/assignments/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export async function apiBulkAssignments(body: {
    assignment_ids: number[];
    primary_user_id?: number | null;
    evaluate?: boolean | null;
}) {
    return request<{
        ok: boolean;
        updated: number;
        errors: string[];
        primary_fio: string | null;
    }>("/api/admin/assignment-bulk", { method: "POST", body: JSON.stringify(body) });
}

export async function apiUsers(role?: string, all = false) {
    const qs = new URLSearchParams();
    if (role) qs.set("role", role);
    if (all) qs.set("all", "true");
    const suffix = qs.toString() ? `?${qs}` : "";
    return request<AdminUser[]>(`/api/admin/users${suffix}`);
}

export async function apiPatchUser(
    id: number,
    body: {
        role?: string;
        site_code?: string | null;
        site_name?: string | null;
        status?: string;
        password?: string;
    },
) {
    return request<{ ok: boolean; user: AdminUser }>(`/api/admin/users/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
    });
}

export async function apiCreateUser(body: {
    tab_no: string;
    fio: string;
    role: string;
    site_code?: string | null;
    site_name?: string | null;
    status?: string;
    password: string;
}) {
    return request<{ ok: boolean; user_id: number }>("/api/admin/users", {
        method: "POST",
        body: JSON.stringify(body),
    });
}

export async function apiSecondEvaluation() {
    return request<SecondEvalRow[]>("/api/admin/second-evaluation");
}

export async function apiAssignSecondary(body: {
    assignment_ids: number[];
    secondary_user_id: number | null;
}) {
    return request<{ ok: boolean; updated: number; errors: string[]; secondary_fio: string | null }>(
        "/api/admin/second-evaluation/assign",
        { method: "POST", body: JSON.stringify(body) },
    );
}

export async function apiImportTariffGrid(file: File) {
    const headers = new Headers();
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const form = new FormData();
    form.append("grid_file", file);
    const res = await fetch(apiUrl("/api/admin/import/tariff-grid"), { method: "POST", headers, body: form });
    if (!res.ok) {
        let detail = res.statusText;
        try {
            const body = await res.json();
            detail = body.detail || JSON.stringify(body);
        } catch {
            /* ignore */
        }
        throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return res.json() as Promise<{ source: string; added: number; updated: number; skipped: number; errors: string[] }[]>;
}

export type DailyImportResult = {
    source: string;
    added: number;
    updated: number;
    skipped: number;
    errors: string[];
};

export async function apiImportDailyAssignees(file: File) {
    const headers = new Headers();
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const form = new FormData();
    form.append("daily_file", file);
    const res = await fetch(apiUrl("/api/admin/import/daily-assignees"), { method: "POST", headers, body: form });
    if (!res.ok) {
        let detail = res.statusText;
        try {
            const body = await res.json();
            detail = body.detail || JSON.stringify(body);
        } catch {
            /* ignore */
        }
        throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return res.json() as Promise<DailyImportResult>;
}

export async function apiTariffGrid() {
    return request<TariffGridRow[]>("/api/admin/tariff-grid");
}

export async function apiPatchEmployee(
    id: number,
    body: { hourly_rate?: number | null; rate_last_raised?: string | null },
) {
    return request<AdminEmployee>(`/api/admin/employees/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
    });
}

export async function apiEmployees(params?: { q?: string; candidates?: boolean }) {
    const qs = new URLSearchParams();
    if (params?.q) qs.set("q", params.q);
    if (params?.candidates) qs.set("candidates_only", "true");
    const suffix = qs.toString() ? `?${qs}` : "";
    return request<AdminEmployee[]>(`/api/admin/employees${suffix}`);
}

export async function apiCreateEmployee(body: Record<string, unknown>) {
    return request("/api/admin/employees", { method: "POST", body: JSON.stringify(body) });
}

export async function apiFormalizeCandidate(body: {
    employee_id: number;
    new_tab_no: string;
    hire_date?: string | null;
    position_1c?: string | null;
}) {
    return request("/api/admin/employees/formalize-candidate", {
        method: "POST",
        body: JSON.stringify(body),
    });
}

export async function apiCreateUrgent(body: {
    employee_id: number;
    evaluator_user_ids: number[];
    comment?: string;
}) {
    return request("/api/admin/urgent", { method: "POST", body: JSON.stringify(body) });
}

export async function apiListUrgent() {
    return request<
        {
            id: number;
            fio: string;
            tab_no: string;
            status: string;
            comment: string | null;
            employee_id: number;
            evaluator_ids: number[];
        }[]
    >("/api/admin/urgent");
}

export async function apiCloseUrgent(id: number) {
    return request(`/api/admin/urgent/${id}/close`, { method: "POST" });
}

export async function apiDelegations() {
    return request<
        {
            id: number;
            original_user_id: number;
            substitute_user_id: number;
            starts_on: string;
            ends_on: string;
            reason: string | null;
            is_active: boolean;
        }[]
    >("/api/admin/delegations");
}

export async function apiCreateDelegation(body: {
    original_user_id: number;
    substitute_user_id: number;
    starts_on: string;
    ends_on: string;
    reason?: string;
}) {
    return request("/api/admin/delegations", { method: "POST", body: JSON.stringify(body) });
}

export async function apiDeactivateDelegation(id: number) {
    return request(`/api/admin/delegations/${id}/deactivate`, { method: "POST" });
}

export async function apiTickets() {
    return request<Ticket[]>("/api/admin/tickets");
}

export async function apiPatchTicket(
    id: number,
    body: { status?: string; admin_note?: string },
) {
    return request<Ticket>(`/api/admin/tickets/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export async function apiEvents(limit = 50) {
    return request<
        { id: number; entity_type: string; entity_id: number | null; action: string; created_at: string | null }[]
    >(`/api/admin/events?limit=${limit}`);
}

export async function apiEscalations() {
    return request<
        {
            user_id: number;
            fio: string;
            tab_no: string;
            pending_assignments: number;
            submitted: number;
            last_login_at: string | null;
        }[]
    >("/api/admin/escalations");
}