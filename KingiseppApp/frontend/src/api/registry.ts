import { request } from "./shared";
import type { Questionnaire } from "./field";

export type RegistryRow = {
    tab_no: string;
    fio: string;
    position: string | null;
    site_name: string | null;
    primary_fio: string | null;
    primary_avg: number | null;
    secondary_fio: string | null;
    secondary_avg: number | null;
    combined_avg?: number | null;
    k_vyr: number | null;
    final_score: number | null;
    status: string;
    hourly_rate: number | null;
    rate_updated_at: string | null;
    rate_last_raised: string | null;
    months_since_rate_update: number | null;
    tariff_stale: boolean;
    is_rate_expired: boolean;
    tariff_min: number | null;
    tariff_max: number | null;
    citizenship: string | null;
    employee_id: number | null;
    assignment_id: number | null;
    probation_end_date?: string | null;
    probation_active?: boolean;
};

export async function apiRegistryRows() {
    return request<RegistryRow[]>("/api/registry/rows");
}

export async function apiQuestionnaire(assignmentId: number) {
    return request<Questionnaire>(`/api/registry/questionnaire/${assignmentId}`);
}

export async function apiUpsertKvyr(body: {
    employee_id?: number | null;
    site_code?: string | null;
    coeff: number;
    comment?: string;
}) {
    return request("/api/registry/kvyr", { method: "POST", body: JSON.stringify(body) });
}