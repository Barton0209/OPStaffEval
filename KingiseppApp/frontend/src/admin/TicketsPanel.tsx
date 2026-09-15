import type { Ticket } from "../api";

type Props = {
    tickets: Ticket[];
    replyDrafts: Record<number, string>;
    onReplyDraft: (id: number, v: string) => void;
    busy: boolean;
    onSendReply: (t: Ticket) => void;
    onCloseTicket: (t: Ticket) => void;
};

export function TicketsPanel({ tickets, replyDrafts, onReplyDraft, busy, onSendReply, onCloseTicket }: Props) {
    return (
        <section className="panel form-panel">
            <h2>Обращения с площадки</h2>
            <p className="muted">Видно, кто написал. Можно ответить мастеру — он увидит ответ в своём списке обращений.</p>
            <div className="ticket-list">
                {tickets.length === 0 && <p className="muted">Обращений пока нет</p>}
                {tickets.map((t) => (
                    <article key={t.id} className="ticket-card">
                        <div className="ticket-card-head">
                            <strong>№{t.id}</strong>
                            <span className={`pill ${t.status === "done" ? "ok" : t.status === "new" ? "warn" : "info"}`}>
                                {t.status === "done" ? "закрыто" : t.status === "new" ? "новое" : "в работе"}
                            </span>
                            <span className="muted">{t.created_at}</span>
                        </div>
                        <p>
                            <strong>От кого:</strong> {t.created_by_fio || "—"}{" "}
                            <span className="muted">({t.created_by_tab_no || t.created_by_user_id})</span>
                        </p>
                        <p>
                            <strong>Сообщение:</strong> {t.message}
                        </p>
                        {t.admin_note && (
                            <p className="ok-text">
                                <strong>Ваш ответ:</strong> {t.admin_note}
                            </p>
                        )}
                        <label>
                            Ответ мастеру
                            <textarea
                                rows={2}
                                placeholder="Напишите ответ…"
                                value={replyDrafts[t.id] ?? t.admin_note ?? ""}
                                onChange={(e) => onReplyDraft(t.id, e.target.value)}
                            />
                        </label>
                        <div className="row">
                            <button
                                type="button"
                                className="primary"
                                disabled={busy}
                                onClick={() => void onSendReply(t)}
                            >
                                Отправить ответ
                            </button>
                            {t.status !== "done" && (
                                <button type="button" onClick={() => void onCloseTicket(t)}>
                                    Закрыть обращение
                                </button>
                            )}
                        </div>
                    </article>
                ))}
            </div>
        </section>
    );
}