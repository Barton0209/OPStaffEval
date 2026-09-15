import { request } from "./shared";

export type NotificationItem = {
    assignment_id: number;
    employee_id: number;
    fio: string;
    tab_no: string;
    site_name: string | null;
    my_role: "primary" | "secondary";
};

export type NotificationsResult = {
    count: number;
    items: NotificationItem[];
};

/** Счётчик неоценённых анкет текущего пользователя. */
export async function apiNotifications(): Promise<NotificationsResult> {
    return request<NotificationsResult>("/api/notifications");
}