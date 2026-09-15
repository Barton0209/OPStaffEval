import { request } from "./shared";

export type EconomistEmployee = {
    id: number;
    tab_no: string;
    fio: string;
    position_1c: string | null;
    department_1c: string | null;
    category: string | null;
    citizenship: string | null;
    hire_date: string | null;
    probation_end_date: string | null;
    is_candidate: boolean;
    hourly_rate: number | null;
    rate_last_raised: string | null;
    is_rate_expired: boolean;
    tariff_min: number | null;
    tariff_max: number | null;
};

export type RateHistoryRow = {
    id: number;
    employee_id: number;
    old_rate: number | null;
    new_rate: number;
    changed_at: string;
    comment: string | null;
    created_at: string | null;
};

export type MissingRateItem = {
    id: number;
    tab_no: string;
    fio: string;
    position_1c: string | null;
    category: string | null;
};

/** Список сотрудников для формы экономиста (поиск по табельному/ФИО + ЧТС). */
export async function apiEconomistEmployees(params?: {
    q?: string;
    missingRateOnly?: boolean;
    limit?: number;
}) {
    const qs = new URLSearchParams();
    if (params?.q) qs.set("q", params.q);
    if (params?.missingRateOnly) qs.set("missing_rate_only", "true");
    if (params?.limit) qs.set("limit", String(params.limit));
    const suffix = qs.toString() ? `?${qs}` : "";
    return request<EconomistEmployee[]>(`/api/economist/employees${suffix}`);
}

/** Изменение ЧТС сотрудника (табельный, дата, новая ставка, комментарий). */
export async function apiEconomistUpdateRate(body: {
    tab_no: string;
    changed_at: string;
    new_rate: number;
    comment?: string | null;
}) {
    return request<{
        id: number;
        tab_no: string;
        fio: string;
        position_1c: string | null;
        category: string | null;
        citizenship: string | null;
        hourly_rate: number;
        rate_last_raised: string;
        is_rate_expired: boolean;
        tariff_min: number | null;
        tariff_max: number | null;
    }>("/api/economist/update-rate", { method: "POST", body: JSON.stringify(body) });
}

/** Бейдж: счётчик сотрудников с незаполненной ЧТС. */
export async function apiEconomistMissingRates() {
    return request<{ count: number; items: MissingRateItem[] }>("/api/economist/missing-rates");
}

/** История изменения ЧТС сотрудника. */
export async function apiEconomistRateHistory(employeeId: number) {
    return request<RateHistoryRow[]>(`/api/economist/rate-history?employee_id=${employeeId}`);
}