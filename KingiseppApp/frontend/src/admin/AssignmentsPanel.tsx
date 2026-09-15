import type { AdminAssignment, AdminUser } from "../api";
import { ExcelSheet, type ExcelColumn } from "../ExcelSheet";
import type { FilterMode } from "./common";

export type MasterCount = { fio: string; role: string; n: number; userId: number };

type Props = {
    assignments: AdminAssignment[];
    filteredAssignments: AdminAssignment[];
    visibleAssignRows: AdminAssignment[];
    onVisibleRowsChange: (rows: AdminAssignment[]) => void;
    assignStats: { total: number; withPrimary: number; awaiting: number; onEval: number; dual: number };
    assignQ: string;
    onAssignQ: (v: string) => void;
    selectedMasterId: string;
    onSelectedMasterId: (v: string) => void;
    masters: AdminUser[];
    masterCounts: MasterCount[];
    selectedMaster: AdminUser | null;
    filterMode: FilterMode;
    onFilterMode: (m: FilterMode) => void;
    columns: ExcelColumn<AdminAssignment>[];
    busy: boolean;
    selectedIds: number[];
    onSelectedIds: (ids: number[]) => void;
    onBulk: (opts: { primary?: boolean; evaluate?: boolean }) => void;
    onToggleSelectAll: () => void;
    onReload: () => Promise<void>;
};

export function AssignmentsPanel({
    assignments,
    filteredAssignments,
    visibleAssignRows,
    onVisibleRowsChange,
    assignStats,
    assignQ,
    onAssignQ,
    selectedMasterId,
    onSelectedMasterId,
    masters,
    masterCounts,
    selectedMaster,
    filterMode,
    onFilterMode,
    columns,
    busy,
    selectedIds,
    onSelectedIds,
    onBulk,
    onToggleSelectAll,
    onReload,
}: Props) {
    return (
        <section className="panel excel-panel">
            <h2>Закрепление: сотрудник → прораб / мастер</h2>
            <p className="muted" style={{ marginTop: 0 }}>
                В реестре {assignStats.total} человек: с оценщиком {assignStats.withPrimary}, без оценщика{" "}
                {assignStats.awaiting}.
            </p>

            <div className="assign-view-tabs">
                <button
                    type="button"
                    className={filterMode === "with_primary" ? "active" : ""}
                    onClick={() => onFilterMode("with_primary")}
                >
                    С оценщиком · {assignStats.withPrimary}
                </button>
                <button
                    type="button"
                    className={filterMode === "awaiting" ? "active" : ""}
                    onClick={() => onFilterMode("awaiting")}
                >
                    Без оценщика · {assignStats.awaiting}
                </button>
                <button
                    type="button"
                    className={filterMode === "evaluate" ? "active" : ""}
                    onClick={() => onFilterMode("evaluate")}
                >
                    На оценке · {assignStats.onEval}
                </button>
                <button
                    type="button"
                    className={filterMode === "dual" ? "active" : ""}
                    onClick={() => onFilterMode("dual")}
                >
                    Двойная · {assignStats.dual}
                </button>
                <button
                    type="button"
                    className={filterMode === "all" ? "active" : ""}
                    onClick={() => onFilterMode("all")}
                >
                    Весь реестр · {assignStats.total}
                </button>
            </div>

            <div className="bulk-bar panel assign-control-bar">
                <label className="toolbar-select assign-master-select">
                    Прораб / мастер
                    <select
                        value={selectedMasterId}
                        onChange={(e) => {
                            const id = e.target.value;
                            onSelectedMasterId(id);
                            if (id && filterMode === "awaiting") {
                                /* оставляем «Без оценщика» — назначаем им выбранного */
                            } else if (id) {
                                onFilterMode("with_primary");
                            }
                        }}
                    >
                        <option value="">— все оценщики —</option>
                        {masters.map((m) => {
                            const n = masterCounts.find((c) => c.userId === m.id)?.n ?? 0;
                            return (
                                <option key={m.id} value={m.id}>
                                    {m.fio} · {m.role === "master" ? "мастер" : "прораб"}
                                    {n ? ` · ${n} чел.` : ""}
                                </option>
                            );
                        })}
                    </select>
                </label>
                <input
                    className="assign-search"
                    placeholder="Поиск: ФИО или табельный"
                    value={assignQ}
                    onChange={(e) => onAssignQ(e.target.value)}
                />
                <button type="button" onClick={() => void onReload()}>
                    Обновить
                </button>
                <span className="muted">
                    На экране: <strong>{filteredAssignments.length}</strong>
                    {selectedIds.length ? ` · отмечено ${selectedIds.length}` : ""}
                </span>
            </div>

            <div className="bulk-bar panel">
                <p className="muted" style={{ margin: 0, flex: "1 1 100%" }}>
                    {selectedMaster ? (
                        <>
                            Выбран: <strong>{selectedMaster.fio}</strong>. Отметьте людей галочками, затем назначьте им этого
                            оценщика. После назначения нажмите «Отправить на оценку» — список появится у него в кабинете.
                        </>
                    ) : (
                        <>Сначала выберите прораба/мастера в списке выше. Затем отметьте сотрудников и назначьте их ему.</>
                    )}
                </p>
                <button
                    type="button"
                    className="primary"
                    disabled={busy || !selectedIds.length || !selectedMasterId}
                    onClick={() => onBulk({ primary: true })}
                    title="Прописать выбранным сотрудникам этого прораба/мастера как основного оценщика"
                >
                    Назначить отмеченных → {selectedMaster ? selectedMaster.fio.split(" ").slice(0, 2).join(" ") : "…"}
                </button>
                <button
                    type="button"
                    className="primary"
                    disabled={busy || !selectedIds.length}
                    onClick={() => onBulk({ evaluate: true })}
                    title="Показать отмеченных в личном кабинете оценщика для заполнения анкеты"
                >
                    Отправить на оценку
                </button>
                <button
                    type="button"
                    disabled={busy || !selectedIds.length}
                    onClick={() => onBulk({ evaluate: false })}
                    title="Убрать отмеченных из списка оценки у прораба/мастера (закрепление остаётся)"
                >
                    Снять с оценки
                </button>
                <button type="button" className="ghost" disabled={busy} onClick={onToggleSelectAll}>
                    Отметить всех на экране
                </button>
                <button type="button" className="ghost" disabled={!selectedIds.length} onClick={() => onSelectedIds([])}>
                    Снять отметки
                </button>
            </div>

            <div className="assign-select-all-bar">
                <label className="check">
                    <input
                        type="checkbox"
                        checked={
                            (visibleAssignRows.length ? visibleAssignRows : filteredAssignments).length > 0 &&
                            (visibleAssignRows.length ? visibleAssignRows : filteredAssignments).every((a) =>
                                selectedIds.includes(a.assignment_id),
                            )
                        }
                        onChange={onToggleSelectAll}
                    />
                    Отметить всех на экране (с учётом фильтров колонок)
                </label>
            </div>

            <ExcelSheet
                rows={filteredAssignments}
                columns={columns}
                rowKey={(a) => a.assignment_id}
                rowClassName={(a) => (!a.primary_user_id ? "xls-warn" : undefined)}
                onVisibleRowsChange={onVisibleRowsChange}
                emptyText={
                    selectedMasterId && filterMode !== "awaiting"
                        ? "У этого оценщика пока никого нет. Откройте «Без оценщика», отметьте людей и нажмите «Назначить»."
                        : "Нет строк. Смените вкладку сверху или сбросьте поиск / фильтры в заголовках."
                }
            />
        </section>
    );
}