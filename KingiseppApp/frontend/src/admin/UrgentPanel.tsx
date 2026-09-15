import type { AdminEmployee, AdminUser } from "../api";
import { ExcelSheet, type ExcelColumn } from "../ExcelSheet";
import type { UrgentItem } from "./common";

type Props = {
    openUrgent: UrgentItem[];
    closedUrgent: UrgentItem[];
    showClosed: boolean;
    onShowClosed: (v: boolean) => void;
    columns: ExcelColumn<UrgentItem>[];
    employees: AdminEmployee[];
    empQ: string;
    onEmpQ: (v: string) => void;
    empId: string;
    onEmpId: (v: string) => void;
    empCandidates: AdminEmployee[];
    selectedEmp: AdminEmployee | null;
    masters: AdminUser[];
    evalQ: string;
    onEvalQ: (v: string) => void;
    evalIds: number[];
    onEvalIds: (ids: number[]) => void;
    masterCandidates: AdminUser[];
    comment: string;
    onComment: (v: string) => void;
    busy: boolean;
    onCreate: () => void;
};

export function UrgentPanel({
    openUrgent,
    closedUrgent,
    showClosed,
    onShowClosed,
    columns,
    employees,
    empQ,
    onEmpQ,
    empId,
    onEmpId,
    empCandidates,
    selectedEmp,
    masters,
    evalQ,
    onEvalQ,
    evalIds,
    onEvalIds,
    masterCandidates,
    comment,
    onComment,
    busy,
    onCreate,
}: Props) {
    return (
        <section className="panel urgent-panel">
            <div className="urgent-head">
                <div className="urgent-head-line">
                    <h2>Срочная оценка</h2>
                    <span className="muted">
                        внеплановая анкета: сотрудник + оценщики · одна открытая заявка на человека
                    </span>
                </div>
                <div className="urgent-stats">
                    <span className="pill warn">Открыто · {openUrgent.length}</span>
                    <span className="pill">В архиве · {closedUrgent.length}</span>
                </div>
            </div>

            <div className="urgent-create">
                <div className="urgent-step">
                    <div className="urgent-step-num">1</div>
                    <div className="urgent-step-body">
                        <strong>Кого оценить</strong>
                        <input
                            placeholder="Поиск: ФИО или табельный номер"
                            value={empQ}
                            onChange={(e) => {
                                onEmpQ(e.target.value);
                                onEmpId("");
                            }}
                        />
                        {selectedEmp ? (
                            <div className="urgent-selected">
                                <div>
                                    <strong>{selectedEmp.fio}</strong>
                                    <div className="muted">{selectedEmp.tab_no}</div>
                                </div>
                                <button
                                    type="button"
                                    className="ghost"
                                    onClick={() => {
                                        onEmpId("");
                                        onEmpQ("");
                                    }}
                                >
                                    Сменить
                                </button>
                            </div>
                        ) : (
                            empQ.trim().length >= 2 && (
                                <div className="urgent-suggest">
                                    {empCandidates.length === 0 ? (
                                        <p className="muted">Никого не найдено</p>
                                    ) : (
                                        empCandidates.map((e) => {
                                            const hasOpen = openUrgent.some((u) => u.employee_id === e.id);
                                            return (
                                                <button
                                                    key={e.id}
                                                    type="button"
                                                    className={`urgent-suggest-item ${hasOpen ? "blocked" : ""}`}
                                                    disabled={hasOpen}
                                                    onClick={() => {
                                                        onEmpId(String(e.id));
                                                        onEmpQ(e.fio);
                                                    }}
                                                >
                                                    <span>
                                                        <strong>{e.fio}</strong>
                                                        <span className="muted"> · {e.tab_no}</span>
                                                    </span>
                                                    {hasOpen && <span className="pill danger">уже открыта</span>}
                                                </button>
                                            );
                                        })
                                    )}
                                </div>
                            )
                        )}
                    </div>
                </div>

                <div className="urgent-step">
                    <div className="urgent-step-num">2</div>
                    <div className="urgent-step-body">
                        <strong>Кто оценивает</strong>
                        <input
                            placeholder="Поиск мастера / прораба"
                            value={evalQ}
                            onChange={(e) => onEvalQ(e.target.value)}
                        />
                        <div className="urgent-chips">
                            {masterCandidates.map((m) => {
                                const on = evalIds.includes(m.id);
                                return (
                                    <button
                                        key={m.id}
                                        type="button"
                                        className={`urgent-chip ${on ? "on" : ""}`}
                                        onClick={() =>
                                            onEvalIds(on ? evalIds.filter((id) => id !== m.id) : [...evalIds, m.id])
                                        }
                                    >
                                        {m.fio.split(" ").slice(0, 2).join(" ")}
                                        <span className="muted">
                                            {" "}
                                            · {m.role === "master" ? "мастер" : "прораб"}
                                        </span>
                                    </button>
                                );
                            })}
                        </div>
                        {evalIds.length > 0 && (
                            <p className="muted" style={{ margin: "0.35rem 0 0" }}>
                                Выбрано:{" "}
                                {masters
                                    .filter((m) => evalIds.includes(m.id))
                                    .map((m) => m.fio.split(" ").slice(0, 2).join(" "))
                                    .join(", ")}
                            </p>
                        )}
                    </div>
                </div>

                <div className="urgent-step">
                    <div className="urgent-step-num">3</div>
                    <div className="urgent-step-body">
                        <strong>Комментарий (необязательно)</strong>
                        <input
                            placeholder="Например: увольнение / перевод / запрос руководства"
                            value={comment}
                            onChange={(e) => onComment(e.target.value)}
                        />
                        <button
                            type="button"
                            className="primary urgent-create-btn"
                            disabled={busy || !empId || evalIds.length === 0}
                            onClick={() => void onCreate()}
                        >
                            Создать срочную оценку
                        </button>
                    </div>
                </div>
            </div>

            <div className="urgent-table-block">
                <div className="urgent-table-tabs">
                    <button
                        type="button"
                        className={!showClosed ? "active" : ""}
                        onClick={() => onShowClosed(false)}
                    >
                        Открытые · {openUrgent.length}
                    </button>
                    <button
                        type="button"
                        className={showClosed ? "active" : ""}
                        onClick={() => onShowClosed(true)}
                    >
                        Архив · {closedUrgent.length}
                    </button>
                </div>

                <ExcelSheet
                    rows={showClosed ? closedUrgent : openUrgent}
                    columns={columns}
                    rowKey={(u) => u.id}
                    emptyText={
                        showClosed ? "Архив пуст — закрытых заявок нет" : "Нет открытых срочных заявок"
                    }
                />
            </div>
        </section>
    );
}