const TOKEN_KEY = "kingisepp_token";
const USER_KEY = "kingisepp_user";
const API_BASE_KEY = "kingisepp_api_base";

// Временно: sessionStorage вместо localStorage.
// TODO: перейти на httpOnly cookie при реализации backend-side session management.
const storage = typeof window !== "undefined" ? window.sessionStorage : null;

export type SessionUser = {
    id?: number;
    access_token?: string;
    tab_no: string;
    fio: string;
    role: string;
    organization_id: number;
    site_code?: string | null;
    site_name?: string | null;
    must_change_password?: boolean;
};

/** Глобальный обработчик «требуется смена пароля» (вызывается при 403 + X-Require-Password-Change). */
let requirePasswordChangeHandler: (() => void) | null = null;

export function setRequirePasswordChangeHandler(fn: (() => void) | null) {
    requirePasswordChangeHandler = fn;
}

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

export type SaveEvaluationResult = {
    id: number;
    avg_score: number | null;
    conflict: boolean;
    conflict_message: string | null;
    status: string;
    conflict_diff?: {
        current_version?: number;
        submitted_version?: number | null;
        server_changes?: Record<string, unknown> | null;
        changed_at?: string | null;
    } | null;
};

export async function request<T>(
    path: string,
    init: RequestInit = {},
    opts?: { timeoutMs?: number },
): Promise<T> {
    const headers = new Headers(init.headers || {});
    if (init.body) headers.set("Content-Type", "application/json");
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const url = apiUrl(path);
    const timeoutMs = opts?.timeoutMs ?? 45000;
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => ctrl.abort(), timeoutMs);
    try {
        const res = await fetch(url, { ...init, headers, signal: ctrl.signal });
        // Мягкое продление сессии: сервер может вернуть новый токен в заголовке.
        // Токены функционально эквивалентны (тот же tv, позже exp) — перезапись безопасна.
        const newToken = res.headers.get("X-New-Token");
        if (newToken && newToken !== storage?.getItem(TOKEN_KEY)) {
            storage?.setItem(TOKEN_KEY, newToken);
            const rawUser = storage?.getItem(USER_KEY);
            if (rawUser) {
                try {
                    const u = JSON.parse(rawUser);
                    u.access_token = newToken;
                    storage?.setItem(USER_KEY, JSON.stringify(u));
                } catch {
                    /* ignore */
                }
            }
        }
        if (!res.ok) {
            if (res.status === 403 && res.headers.get("X-Require-Password-Change") === "true") {
                requirePasswordChangeHandler?.();
                const err = new Error("Требуется смена пароля");
                (err as unknown as { requirePasswordChange: boolean }).requirePasswordChange = true;
                throw err;
            }
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
    } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") {
            throw new Error(
                `Сервер не отвечает (таймаут ${Math.round(timeoutMs / 1000)} с). Проверьте туннель/связь и попробуйте ещё раз.`,
            );
        }
        throw e;
    } finally {
        window.clearTimeout(timer);
    }
}

/** Базовый адрес сервера. Пусто = тот же хост (веб из FastAPI). В Android APK обязателен. */
export function getApiBase(): string {
    const saved = storage?.getItem(API_BASE_KEY);
    if (saved != null) return saved.replace(/\/$/, "");
    return (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") || "";
}

export function setApiBase(url: string) {
    const cleaned = url.trim().replace(/\/$/, "");
    storage?.setItem(API_BASE_KEY, cleaned);
}

export function clearApiBase() {
    storage?.removeItem(API_BASE_KEY);
}

export function apiUrl(path: string): string {
    const base = getApiBase();
    if (!base) return path;
    if (path.startsWith("http")) return path;
    return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}

export function getToken(): string | null {
    return storage?.getItem(TOKEN_KEY) ?? null;
}

export function clearSession() {
    storage?.removeItem(TOKEN_KEY);
    storage?.removeItem(USER_KEY);
}

export async function apiHealth(): Promise<{ status: string; app: string; org: string }> {
    return request("/api/health");
}

/** Скачивание файла с авторизацией (Excel/PDF выгрузки). */
export async function apiDownload(path: string, filename: string, init: RequestInit = {}) {
    const token = getToken();
    const headers = new Headers(init.headers || {});
    if (init.body) headers.set("Content-Type", "application/json");
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const res = await fetch(apiUrl(path), { ...init, headers });
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
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
}

/** Сохранённый пользователь сессии (для восстановления UI при requirePasswordChange). */
export function getStoredUser(): SessionUser | null {
    const raw = storage?.getItem(USER_KEY);
    if (!raw) return null;
    try {
        return JSON.parse(raw) as SessionUser;
    } catch {
        return null;
    }
}