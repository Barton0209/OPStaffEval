import { useState } from "react";
import type { AdminEmployee } from "../api";

type Props = {
    employees: AdminEmployee[];
    empQ: string;
    onEmpQ: (v: string) => void;
    candOnly: boolean;
    onCandOnly: (v: boolean) => void;
    newTab: string;
    onNewTab: (v: string) => void;
    newFio: string;
    onNewFio: (v: string) => void;
    formalizeId: string;
    onFormalizeId: (v: string) => void;
    formalizeTab: string;
    onFormalizeTab: (v: string) => void;
    busy: boolean;
    onApply: () => void;
    onAdd: () => void;
    onFormalize: () => void;
    onPatchRate: (emp: AdminEmployee, newRate: number) => Promise<void>;
};

/** Красная подсветка просроченной ЧТС (>= 180 дней без поднятия). */
export function rateExpiredClass(expired: boolean | undefined): string {
    return expired ? "rate-expired" : "";
}

export function RateCell({
    emp,
    busy,
    onPatchRate,
}: {
    emp: AdminEmployee;
    busy: boolean;
    onPatchRate: (emp: AdminEmployee, newRate: number) => Promise<void>;
}) {
    const [draft, setDraft] = useState<string>(emp.hourly_rate != null ? String(emp.hourly_rate) : "");
    const [saving, setSaving] = useState(false);

    const value = Number(draft);
    const dirty =
        draft.trim() !== "" &&
        !Number.isNaN(value) &&
        value > 0 &&
        value !== (emp.hourly_rate ?? 0);

    async function save() {
        if (!dirty) return;
        setSaving(true);
        try {
            await onPatchRate(emp, value);
        } finally {
            setSaving(false);
        }
    }

    return (
        <div className="rate-edit-cell">
            <input
                className="rate-input"
                type="number"
                min="0"
                step="0.01"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                aria-label={`ЧТС ${emp.fio}`}
            />
            {emp.is_rate_expired && (
                <span className="rate-expired-mark" title="ЧТС не повышалась более 6 месяцев!">
                    ⚠
                </span>
            )}
            <button
                type="button"
                className="primary xls-save-btn"
                disabled={busy || saving || !dirty}
                onClick={() => void save()}
            >
                {saving ? "…" : "Сохр."}
            </button>
        </div>
    );
}

export function EmployeesPanel({
    employees,
    empQ,
    onEmpQ,
    candOnly,
    onCandOnly,
    newTab,
    onNewTab,
    newFio,
    onNewFio,
    formalizeId,
    onFormalizeId,
    formalizeTab,
    onFormalizeTab,
    busy,
    onApply,
    onAdd,
    onFormalize,
    onPatchRate,
}: Props) {
    return (
        <section className="panel excel-panel">
            <h2>База сотрудников</h2>
            <div className="excel-toolbar">
                <input
                    placeholder="Фильтр ФИО / таб.№"
                    value={empQ}
                    onChange={(e) => onEmpQ(e.target.value)}
                />
                <button type="button" onClick={() => void onApply()}>
                    Применить
                </button>
                <label className="check">
                    <input type="checkbox" checked={candOnly} onChange={(e) => onCandOnly(e.target.checked)} />
                    только кандидаты
                </label>
            </div>
            <div className="row">
                <input placeholder="Табельный №" value={newTab} onChange={(e) => onNewTab(e.target.value)} />
                <input placeholder="ФИО" value={newFio} onChange={(e) => onNewFio(e.target.value)} />
                <button type="button" disabled={busy} onClick={() => void onAdd()}>
                    Добавить в базу
                </button>
            </div>
            <div className="row">
                <select value={formalizeId} onChange={(e) => onFormalizeId(e.target.value)}>
                    <option value="">Оформить кандидата…</option>
                    {employees
                        .filter((e) => e.is_candidate)
                        .map((e) => (
                            <option key={e.id} value={e.id}>
                                {e.fio} ({e.tab_no})
                            </option>
                        ))}
                </select>
                <input
                    placeholder="Новый табельный №"
                    value={formalizeTab}
                    onChange={(e) => onFormalizeTab(e.target.value)}
                />
                <button type="button" disabled={busy} onClick={() => void onFormalize()}>
                    Оформить
                </button>
            </div>
            <div className="excel-wrap tall">
                <table className="excel-table sticky">
                    <thead>
                        <tr>
                            <th>id</th>
                            <th>Таб. №</th>
                            <th>ФИО</th>
                            <th>Должность</th>
                            <th>Кандидат</th>
                            <th>Дата приёма</th>
                            <th>ЧТС</th>
                            <th>Дата поднятия ЧТС</th>
                        </tr>
                    </thead>
                    <tbody>
                        {employees.map((e) => (
                            <tr
                                key={e.id}
                                className={[e.is_candidate ? "row-info" : "", rateExpiredClass(e.is_rate_expired)]
                                    .filter(Boolean)
                                    .join(" ") || undefined}
                            >
                                <td>{e.id}</td>
                                <td>{e.tab_no}</td>
                                <td>{e.fio}</td>
                                <td>{e.position_1c || "—"}</td>
                                <td>{e.is_candidate ? "да" : "нет"}</td>
                                <td>{e.hire_date || "—"}</td>
                                <td>
                                    <RateCell emp={e} busy={busy} onPatchRate={onPatchRate} />
                                </td>
                                <td>
                                    {e.rate_last_raised ? (
                                        <span className={rateExpiredClass(e.is_rate_expired)} title="Дата последнего поднятия ЧТС">
                                            {e.rate_last_raised}
                                            {e.is_rate_expired ? " ⚠" : ""}
                                        </span>
                                    ) : (
                                        "—"
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            <p className="muted">
                ЧТС правится прямо в строке (сохранение проставит дату повышения автоматически). Красная строка/значение —
                ЧТС не поднималась более 6 месяцев.
            </p>
        </section>
    );
}