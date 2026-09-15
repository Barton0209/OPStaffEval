import type { Dashboard } from "../api";
import { DashCard, type EscalationRow, type FilterMode, type Tab } from "./common";

type Props = {
    dash: Dashboard;
    progress: number;
    escalations: EscalationRow[];
    onGo: (tab: Tab, opts?: { candidates?: boolean; mode?: FilterMode }) => void;
    onOpenRegistry: () => void;
};

export function DashboardPanel({ dash, progress, escalations, onGo, onOpenRegistry }: Props) {
    return (
        <>
            <section className="hero-card">
                <p className="muted">Период оценки · ВелесстройМонтаж · Кингисепп</p>
                <h1>{dash.period_code}</h1>
                <p className="muted">{dash.organization}</p>
                <div className="progress-block">
                    <div className="progress-meta">
                        <span>
                            Сдано анкет: {dash.submitted_evaluations} из {dash.evaluate_yes}
                        </span>
                        <strong>{progress}%</strong>
                    </div>
                    <div className="progress-bar" aria-hidden>
                        <span style={{ width: `${Math.min(progress, 100)}%` }} />
                    </div>
                </div>
            </section>

            <div className="help-box">
                <strong>Как оценивают с телефона?</strong>
                <span className="muted">
                    Мастер или прораб входит своим табельным — видит свой список и ставит оценки. Здесь отдел
                    мобилизации назначает, кто кого оценивает, и загружает Excel.
                </span>
            </div>

            <section className="dash-grid">
                <DashCard
                    cls="info"
                    icon="📋"
                    label="В реестре закреплений"
                    value={dash.total_assignments}
                    hint="открыть таблицу назначений"
                    tipTitle="Реестр закреплений"
                    tip="Полный реестр всех закреплений сотрудников за оценщиками. Клик — открыть таблицу назначений."
                    onClick={() => onGo("assign", { mode: "all" })}
                />
                <DashCard
                    cls="ok"
                    icon="✅"
                    label="Идут на оценку"
                    value={dash.evaluate_yes}
                    hint="только отмеченные к оценке"
                    tipTitle="Идут на оценку"
                    tip="Сотрудники, отмеченные к оценке в текущем периоде. Клик — фильтр «на оценке»."
                    onClick={() => onGo("assign", { mode: "evaluate" })}
                />
                <DashCard
                    cls=""
                    icon="👤"
                    label="Есть основной оценщик"
                    value={dash.with_primary}
                    hint="с назначенным мастером/ПР"
                    tipTitle="Есть основной оценщик"
                    tip="Закрепления, у которых назначен основной оценщик (мастер/ПР)."
                    onClick={() => onGo("assign", { mode: "with_primary" })}
                />
                <DashCard
                    cls={dash.awaiting_primary ? "warn" : ""}
                    icon="⏳"
                    label="Ждут назначения"
                    value={dash.awaiting_primary}
                    hint="без оценщика — назначить"
                    tipTitle="Ждут назначения"
                    tip="Сотрудники без оценщика — нужно назначить. Клик — список ожидания."
                    onClick={() => onGo("assign", { mode: "awaiting" })}
                />
                <DashCard
                    cls={dash.candidates ? "info" : ""}
                    icon="🆕"
                    label="Кандидаты"
                    value={dash.candidates}
                    hint="открыть базу кандидатов"
                    tipTitle="Кандидаты"
                    tip="Новые кандидаты в базе. Клик — открыть базу кандидатов."
                    onClick={() => onGo("employees", { candidates: true })}
                />
                <DashCard
                    cls=""
                    icon="👥"
                    label="Двойная оценка"
                    value={dash.dual_enabled}
                    hint="два независимых оценщика"
                    tipTitle="Двойная оценка"
                    tip="Закрепления с двумя независимыми оценщиками — для исключения путаницы и коррупции."
                    onClick={() => onGo("assign", { mode: "dual" })}
                />
                <DashCard
                    cls={dash.open_urgent ? "warn" : "ok"}
                    icon="⚡"
                    label="Срочные оценки"
                    value={dash.open_urgent}
                    hint="открытые срочные запросы"
                    tipTitle="Срочные оценки"
                    tip="Открытые срочные запросы с площадки. Клик — вкладка «Срочная»."
                    onClick={() => onGo("urgent")}
                />
                <DashCard
                    cls={dash.open_tickets ? "warn" : "ok"}
                    icon="💬"
                    label="Обращения с площадки"
                    value={dash.open_tickets}
                    hint="ошибки в списках"
                    tipTitle="Обращения с площадки"
                    tip="Обращения об ошибках в списках. Клик — вкладка «Обращения»."
                    onClick={() => onGo("tickets")}
                />
                <DashCard
                    cls={dash.escalations ? "danger" : "ok"}
                    icon="🚨"
                    label="Эскалации"
                    value={dash.escalations}
                    hint="нет входа > 3 дней"
                    tipTitle="Эскалации"
                    tip="Сотрудники без захода в кабинет более 3 дней при незакрытых оценках. Клик — блок эскалаций."
                    onClick={() => document.getElementById("escalations-block")?.scrollIntoView({ behavior: "smooth" })}
                />
                <DashCard
                    cls="ok"
                    icon="📊"
                    label="Сдано анкет"
                    value={dash.submitted_evaluations}
                    hint="открыть реестр итогов"
                    tipTitle="Сдано анкет"
                    tip="Завершённые и сданные оценки. Клик — реестр итогов."
                    onClick={() => onOpenRegistry()}
                />
            </section>

            <section className="panel" id="escalations-block">
                <h2>Кто не заходит в систему</h2>
                <p className="muted">Нет входа больше 3 дней при незакрытых оценках.</p>
                {escalations.length === 0 && <p className="ok-text">Сейчас эскалаций нет.</p>}
                <div className="excel-wrap">
                    <table className="excel-table">
                        <thead>
                            <tr>
                                <th>ФИО</th>
                                <th>Таб. №</th>
                                <th>Осталось</th>
                                <th>Сдано</th>
                                <th>Всего</th>
                            </tr>
                        </thead>
                        <tbody>
                            {escalations.map((e) => (
                                <tr key={e.user_id}>
                                    <td>{e.fio}</td>
                                    <td>{e.tab_no}</td>
                                    <td>{Math.max(e.pending_assignments - e.submitted, 0)}</td>
                                    <td>{e.submitted}</td>
                                    <td>{e.pending_assignments}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </section>
        </>
    );
}