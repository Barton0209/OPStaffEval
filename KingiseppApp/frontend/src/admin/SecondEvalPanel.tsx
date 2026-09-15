import type { AdminUser, SecondEvalRow } from "../api";
import { ExcelSheet, type ExcelColumn } from "../ExcelSheet";
import { nfSite, SECOND_GROUPS, type SecondGroup } from "./common";

type Props = {
    rows: SecondEvalRow[];
    columns: ExcelColumn<SecondEvalRow>[];
    counts: Record<SecondGroup, number>;
    group: SecondGroup;
    onGroup: (g: SecondGroup) => void;
    assignMode: boolean;
    onAssignMode: (v: boolean) => void;
    assignActive: boolean;
    chiefs: AdminUser[];
    chiefId: string;
    onChiefId: (v: string) => void;
    chief: AdminUser | null;
    busy: boolean;
    selected: number[];
    onAssignBulk: () => void;
    onReload: () => Promise<void>;
};

export function SecondEvalPanel({
    rows,
    columns,
    counts,
    group,
    onGroup,
    assignMode,
    onAssignMode,
    assignActive,
    chiefs,
    chiefId,
    onChiefId,
    chief,
    busy,
    selected,
    onAssignBulk,
    onReload,
}: Props) {
    return (
        <section className="panel excel-panel">
            <h2>Вторая оценка</h2>
            <p className="muted" style={{ marginTop: 0 }}>
                Второй независимый оценщик — <strong>начальник участка</strong>. Назначить можно только на сотрудников
                его участка (совпадение по полю «Участок») и только тем, у кого уже есть 1-й оценщик.
            </p>

            <div className="assign-view-tabs">
                {SECOND_GROUPS.map((g) => (
                    <button
                        key={g.id}
                        type="button"
                        className={!assignMode && group === g.id ? "active" : ""}
                        onClick={() => {
                            onGroup(g.id);
                            onAssignMode(false);
                        }}
                    >
                        {g.label} · {counts[g.id]}
                    </button>
                ))}
                <button
                    type="button"
                    className={assignMode ? "active" : ""}
                    onClick={() => {
                        onAssignMode(true);
                    }}
                >
                    Назначить 2 оценщика
                </button>
            </div>

            {assignActive && (
                <div className="bulk-bar panel assign-control-bar">
                    <label className="toolbar-select assign-master-select">
                        Начальник участка
                        <select
                            value={chiefId}
                            onChange={(e) => {
                                onChiefId(e.target.value);
                            }}
                        >
                            <option value="">— выберите начальника участка —</option>
                            {chiefs.map((c) => {
                                const match = rows.filter(
                                    (r) =>
                                        r.primary_user_id &&
                                        !(r.dual_enabled && r.secondary_user_id) &&
                                        c.site_name &&
                                        nfSite(r.site_name) === nfSite(c.site_name),
                                ).length;
                                return (
                                    <option key={c.id} value={c.id}>
                                        {c.fio} · {c.site_name || "участок не указан"}
                                        {match ? ` · доступно ${match} чел.` : ""}
                                    </option>
                                );
                            })}
                        </select>
                    </label>
                    <button
                        type="button"
                        className="primary"
                        disabled={busy || !chief || !selected.length}
                        onClick={() => void onAssignBulk()}
                        title="Назначить выбранного начальника участка 2-м оценщиком отмеченным сотрудникам"
                    >
                        Назначить 2-го → {chief ? chief.fio.split(" ").slice(0, 2).join(" ") : "…"}
                    </button>
                    <button type="button" onClick={() => void onReload()}>
                        Обновить
                    </button>
                    <span className="muted">
                        На экране: <strong>{rows.length}</strong>
                        {selected.length ? ` · отмечено ${selected.length}` : ""}
                    </span>
                </div>
            )}
            {assignActive && chief && (
                <p className="muted" style={{ margin: "0 0 0.6rem" }}>
                    Показаны сотрудники участка <strong>{chief.site_name}</strong>
                    {assignMode ? " с 1-м оценщиком" : " из этой группы"}. Отметьте галочками, кому назначить 2-го.
                    Кнопка «Снять 2-го» убирает текущего 2-го оценщика.
                </p>
            )}
            {assignActive && !chief && (
                <p className="muted" style={{ margin: "0 0 0.6rem" }}>
                    Выберите начальника участка — список сократится до сотрудников его участка.
                </p>
            )}

            <ExcelSheet
                rows={rows}
                columns={columns}
                rowKey={(r) => r.assignment_id}
                rowClassName={(r) =>
                    assignActive &&
                        chief &&
                        r.primary_user_id &&
                        !(r.dual_enabled && r.secondary_user_id)
                        ? undefined
                        : assignActive
                            ? "xls-row-dim"
                            : !r.primary_user_id
                                ? "xls-warn"
                                : undefined
                }
                emptyText={
                    assignActive
                        ? chief
                            ? "На участке этого начальника нет подходящих сотрудников."
                            : "Выберите начальника участка выше."
                        : "Нет строк в этой группе. Переключите группу сверху."
                }
            />
        </section>
    );
}