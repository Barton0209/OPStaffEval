import type { SecondEvalRow } from "../api";

export type Tab =
    | "dash"
    | "assign"
    | "second"
    | "urgent"
    | "delegate"
    | "employees"
    | "tickets"
    | "events"
    | "groups"
    | "settings";

export type SettingsSub = "import" | "masters" | "chiefs" | "admin_imports" | "economist_imports" | "fired";

export type SecondGroup = "all" | "no_evaluators" | "no_secondary" | "on_first" | "got_first";

export type FilterMode = "all" | "evaluate" | "with_primary" | "awaiting" | "dual";

export type UserDraft = {
    role: string;
    site_code: string;
    site_name: string;
    status: string;
    password: string;
};

export type NewUserDraft = {
    tab_no: string;
    fio: string;
    role: string;
    site_code: string;
    site_name: string;
    status: string;
    password: string;
};

export type UrgentItem = {
    id: number;
    fio: string;
    tab_no: string;
    status: string;
    comment: string | null;
    employee_id: number;
    evaluator_names?: string[];
};

export type DelegationRow = {
    id: number;
    original_user_id: number;
    substitute_user_id: number;
    starts_on: string;
    ends_on: string;
    reason: string | null;
    is_active: boolean;
};

export type EventRow = {
    id: number;
    entity_type: string;
    entity_id: number | null;
    action: string;
    created_at: string | null;
};

export type EscalationRow = {
    user_id: number;
    fio: string;
    tab_no: string;
    pending_assignments: number;
    submitted: number;
    last_login_at: string | null;
};

export const ROLE_LABELS: Record<string, string> = {
    master: "Мастер",
    foreman: "Производитель работ",
    site_chief: "Начальник участка",
    admin_op: "Администрация ОП",
    admin: "Админ",
    economist: "Экономист",
};

export const ROLE_ORDER = ["master", "foreman", "site_chief", "economist", "admin_op", "admin"];

export function roleLabel(role: string) {
    return ROLE_LABELS[role] || role;
}

/** Нормализация для сравнения участков */
export function nfSite(s?: string | null) {
    return (s || "").trim().toLowerCase().replace(/\s+/g, " ");
}

export function evalStatusLabel(st: SecondEvalRow["primary_eval_status"]) {
    return st === "submitted" ? "сдана" : st === "draft" ? "в работе" : "не начата";
}

export const SECOND_GROUPS: { id: SecondGroup; label: string; match: (r: SecondEvalRow) => boolean }[] = [
    { id: "all", label: "Все сотрудники", match: () => true },
    {
        id: "no_evaluators",
        label: "Без 1 и 2 оценщика",
        match: (r) => !r.primary_user_id && !(r.dual_enabled && r.secondary_user_id),
    },
    {
        id: "no_secondary",
        label: "Без 2 оценщика",
        match: (r) => !!r.primary_user_id && !(r.dual_enabled && r.secondary_user_id),
    },
    {
        id: "on_first",
        label: "На 1 оценке",
        match: (r) => !!r.primary_user_id && r.primary_eval_status !== "submitted",
    },
    {
        id: "got_first",
        label: "Получили 1 оценку",
        match: (r) => !!r.primary_user_id && r.primary_eval_status === "submitted",
    },
];

export function pct(part: number, total: number) {
    if (!total) return 0;
    return Math.round((part / total) * 100);
}

/** Фирменные фоны — кроссфейд-слайдшоу */
export const BG_IMAGES = [
    "./brand/bg-1.png",
    "./brand/bg-2.png",
    "./brand/bg-3.png",
    "./brand/bg-4.png",
];

/** Карточка сводки со всплывающей подсказкой при наведении */
export function DashCard({
    cls,
    icon,
    label,
    value,
    hint,
    tipTitle,
    tip,
    onClick,
}: {
    cls: string;
    icon: string;
    label: string;
    value: number;
    hint: string;
    tipTitle: string;
    tip: string;
    onClick: () => void;
}) {
    return (
        <button type="button" className={`metric clickable ${cls}`.trim()} onClick={onClick}>
            <div className="metric-ico" aria-hidden>{icon}</div>
            <div className="label">{label}</div>
            <div className="value">{value}</div>
            <div className="hint">{hint}</div>
            <span className="metric-tip" role="tooltip">
                <strong>{tipTitle}</strong>
                <span>{tip}</span>
            </span>
        </button>
    );
}

export const TABS: { id: Tab; label: string; tipTitle: string; tip: string }[] = [
    {
        id: "dash",
        label: "Сводка",
        tipTitle: "Сводка",
        tip: "Общая картина периода: сколько людей на оценке, сдано анкет, срочные и обращения.",
    },
    {
        id: "assign",
        label: "Закрепление",
        tipTitle: "Закрепление",
        tip: "Кто за каким прорабом/мастером. Здесь назначают оценщика и отправляют список на оценку.",
    },
    {
        id: "second",
        label: "Вторая оценка",
        tipTitle: "Вторая оценка",
        tip: "Второй независимый оценщик — начальник участка. Назначается только сотрудникам своего участка.",
    },
    {
        id: "urgent",
        label: "Срочная",
        tipTitle: "Срочная оценка",
        tip: "Внеплановая анкета вне общего списка: выбрать сотрудника и оценщиков, открыть/закрыть заявку.",
    },
    {
        id: "delegate",
        label: "Замещение",
        tipTitle: "Замещение",
        tip: "Временная передача списка оценок другому мастеру/прорабу на период отсутствия.",
    },
    {
        id: "employees",
        label: "База",
        tipTitle: "База сотрудников",
        tip: "Справочник людей из 1С и кандидаты: поиск, добавление, оформление кандидата.",
    },
    {
        id: "tickets",
        label: "Обращения",
        tipTitle: "Обращения",
        tip: "Сообщения с площадки об ошибках в списках. Можно ответить и закрыть обращение.",
    },
    {
        id: "events",
        label: "Журнал",
        tipTitle: "Журнал событий",
        tip: "История действий в системе: импорты, назначения, срочные, изменения.",
    },
    {
        id: "groups",
        label: "Группы",
        tipTitle: "Группы пользователей",
        tip: "Управление связками: Площадка → Отдел → Группа → Пользователи. Фото для фонов.",
    },
    {
        id: "settings",
        label: "Настройки",
        tipTitle: "Настройки",
        tip: "Импорт Excel и управление пользователями: роли, участки, статусы, пароли.",
    },
];