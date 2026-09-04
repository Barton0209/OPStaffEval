const TOKEN_KEY = "kingisepp_token";
const USER_KEY = "kingisepp_user";
const API_BASE_KEY = "kingisepp_api_base";

export type SessionUser = {
  id?: number;
  access_token?: string;
  tab_no: string;
  fio: string;
  role: string;
  organization_id: number;
  site_code?: string | null;
  site_name?: string | null;
};

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
};

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

export type RegistryRow = {
  tab_no: string;
  fio: string;
  position: string | null;
  site_name: string | null;
  primary_fio: string | null;
  primary_avg: number | null;
  secondary_fio: string | null;
  secondary_avg: number | null;
  k_vyr: number | null;
  final_score: number | null;
  status: string;
  hourly_rate: number | null;
  rate_updated_at: string | null;
  months_since_rate_update: number | null;
  tariff_stale: boolean;
  employee_id: number | null;
  assignment_id: number | null;
};

export type AdminUser = {
  id: number;
  tab_no: string;
  fio: string;
  role: string;
  site_code: string | null;
  status: string;
};

export type AdminEmployee = {
  id: number;
  tab_no: string;
  fio: string;
  position_1c: string | null;
  is_candidate: boolean;
  hire_date: string | null;
};

export type AdminAssignment = {
  assignment_id: number;
  employee_id: number;
  tab_no: string;
  fio: string;
  is_candidate: boolean;
  site_code: string | null;
  site_name: string | null;
  evaluate: boolean;
  primary_fio: string | null;
  primary_tab: string | null;
  primary_user_id: number | null;
  dual_enabled: boolean;
  secondary_user_id: number | null;
  worker_status: string | null;
  version: number;
};

export type Ticket = {
  id: number;
  message: string;
  status: string;
  assignment_id: number | null;
  employee_id: number | null;
  created_by_user_id: number;
  created_by_fio?: string | null;
  created_by_tab_no?: string | null;
  admin_note: string | null;
  created_at: string | null;
  updated_at?: string | null;
};

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers || {});
  if (init.body) headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const url = apiUrl(path);
  const res = await fetch(url, { ...init, headers });
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
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

/** Базовый адрес сервера. Пусто = тот же хост (веб из FastAPI). В Android APK обязателен. */
export function getApiBase(): string {
  const saved = localStorage.getItem(API_BASE_KEY);
  if (saved != null) return saved.replace(/\/$/, "");
  return (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") || "";
}

export function setApiBase(url: string) {
  const cleaned = url.trim().replace(/\/$/, "");
  localStorage.setItem(API_BASE_KEY, cleaned);
}

export function clearApiBase() {
  localStorage.removeItem(API_BASE_KEY);
}

export function apiUrl(path: string): string {
  const base = getApiBase();
  if (!base) return path;
  if (path.startsWith("http")) return path;
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}

export async function apiHealth(): Promise<{ status: string; app: string; org: string }> {
  return request("/api/health");
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export async function apiLogin(tab_no: string, password: string): Promise<SessionUser> {
  const data = await request<SessionUser & { access_token: string }>("/api/field/auth/login", {
    method: "POST",
    body: JSON.stringify({ tab_no, password }),
  });
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.setItem(USER_KEY, JSON.stringify(data));
  return data;
}

export async function apiMe(): Promise<SessionUser> {
  return request<SessionUser>("/api/field/me");
}

export async function apiMyAssignments(): Promise<AssignmentItem[]> {
  return request<AssignmentItem[]>("/api/field/assignments");
}

export async function apiSaveEvaluation(
  kind: "assignment" | "urgent",
  id: number,
  body: Record<string, unknown>,
  submit: boolean,
) {
  const path =
    kind === "assignment"
      ? `/api/field/assignments/${id}/evaluation?submit=${submit}`
      : `/api/field/urgent/${id}/evaluation?submit=${submit}`;
  return request<{
    id: number;
    avg_score: number | null;
    conflict: boolean;
    conflict_message: string | null;
    status: string;
  }>(path, { method: "POST", body: JSON.stringify(body) });
}

export async function apiCreateTicket(body: {
  message: string;
  assignment_id?: number | null;
  employee_id?: number | null;
}) {
  return request<Ticket>("/api/field/tickets", { method: "POST", body: JSON.stringify(body) });
}

export async function apiDashboard() {
  return request<Dashboard>("/api/admin/dashboard");
}

export async function apiImportAll() {
  return request<{ source: string; added: number; updated: number; skipped: number; errors: string[] }[]>(
    "/api/admin/import/all",
    { method: "POST" },
  );
}

export async function apiImportUpload(files: {
  base?: File | null;
  users?: File | null;
  carnet?: File | null;
}) {
  const form = new FormData();
  if (files.base) form.append("base_file", files.base);
  if (files.users) form.append("users_file", files.users);
  if (files.carnet) form.append("carnet_file", files.carnet);
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

export async function apiUsers(role?: string) {
  const qs = role ? `?role=${encodeURIComponent(role)}` : "";
  return request<AdminUser[]>(`/api/admin/users${qs}`);
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

export async function apiMyTickets() {
  return request<Ticket[]>("/api/field/tickets");
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

export async function apiRegistryRows() {
  return request<RegistryRow[]>("/api/registry/rows");
}

export async function apiUpsertKvyr(body: {
  employee_id?: number | null;
  site_code?: string | null;
  coeff: number;
  comment?: string;
}) {
  return request("/api/registry/kvyr", { method: "POST", body: JSON.stringify(body) });
}
