import { useEffect, useMemo, useRef, useState } from "react";
import {
  apiCreateTicket,
  apiGetEvaluation,
  apiMyAssignments,
  apiMyTickets,
  apiSaveEvaluation,
  apiSiteOverview,
  type AssignmentItem,
  type SaveEvaluationResult,
  type SessionUser,
  type SiteOverview,
  type Ticket,
} from "./api";
import { enqueueOutbox, flushOutbox, listOutbox } from "./offline";
import { ConflictModal } from "./ConflictModal";
import { NotificationBell } from "./NotificationBell";

const SCALE = [
  { n: 1, title: "неудовлетворительно", hint: "Проявляет качества, противоположные требуемым." },
  { n: 2, title: "удовлетворительно", hint: "Требуемые качества не всегда проявляются." },
  { n: 3, title: "хорошо", hint: "Требуемые качества проявляются в большинстве случаев." },
  { n: 4, title: "очень хорошо", hint: "Требуемые качества проявляются стабильно хорошо." },
  { n: 5, title: "отлично", hint: "Требуемые качества проявляются безупречно и всегда." },
] as const;

const CRITERIA = [
  {
    key: "score_quality",
    title: "Качество выполнения работы и надёжность",
    desc: "Отсутствие брака, переделок и порчи материалов. Качественное выполнение стандартных и сложных задач на своём участке.",
  },
  {
    key: "score_discipline",
    title: "Соблюдение трудовой дисциплины",
    desc: "Своевременный приход на смену, отсутствие простоев и прогулов, соблюдение графика рабочего дня.",
  },
  {
    key: "score_safety",
    title: "Безопасность и охрана труда",
    desc: "Ношение спецодежды и СИЗ, безопасная работа с инструментом и техникой, порядок на рабочем месте.",
  },
  {
    key: "score_skills",
    title: "Профессиональные знания и навыки",
    desc: "Понимание технологии работ, правильное использование материалов, инструментов и оборудования.",
  },
  {
    key: "score_versatility",
    title: "Универсальность и обучаемость",
    desc: "Готовность переключиться на другую задачу, скорость освоения новых приёмов, рост личной выработки.",
  },
] as const;

type Scores = Record<(typeof CRITERIA)[number]["key"], number>;

function emptyScores(): Scores {
  return {
    score_quality: 3,
    score_discipline: 3,
    score_safety: 3,
    score_skills: 3,
    score_versatility: 3,
  };
}

function roleRu(role: string) {
  if (role === "master") return "Мастер";
  if (role === "foreman") return "Прораб (производитель работ)";
  if (role === "site_chief") return "Начальник участка";
  return role;
}

function anketaTitle(role: string) {
  if (role === "foreman") return "Анкета по оценке деятельности рабочего персонала (Производитель работ)";
  if (role === "site_chief") return "Анкета по оценке деятельности рабочего персонала (Начальник участка)";
  return "Анкета по оценке деятельности рабочего персонала (Мастер)";
}

function statusRu(status: string | null, isUrgent: boolean) {
  if (isUrgent) return "Срочно";
  if (!status) return "Нужно оценить";
  if (status === "draft") return "Черновик";
  if (status === "submitted") return "Отправлено";
  return status;
}

type Props = {
  user: SessionUser;
  online: boolean;
  onLogout: () => void;
  onOpenRegistry?: () => void;
};

export function FieldApp({ user, online, onLogout, onOpenRegistry }: Props) {
  const isChief = user.role === "site_chief";
  const [items, setItems] = useState<AssignmentItem[]>([]);
  const [selected, setSelected] = useState<AssignmentItem | null>(null);
  const [scores, setScores] = useState<Scores>(emptyScores());
  const [comment, setComment] = useState("");
  const [ticketMsg, setTicketMsg] = useState("");
  const [showTicket, setShowTicket] = useState(false);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState(0);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [filter, setFilter] = useState("");
  const [listMode, setListMode] = useState<"todo" | "done" | "urgent">("todo");
  const [readOnly, setReadOnly] = useState(false);
  const [loadingForm, setLoadingForm] = useState(false);
  const [myTickets, setMyTickets] = useState<Ticket[]>([]);
  const [showMyTickets, setShowMyTickets] = useState(false);
  const [overview, setOverview] = useState<SiteOverview | null>(null);
  const [showOverview, setShowOverview] = useState(true);
  const [conflictData, setConflictData] = useState<SaveEvaluationResult | null>(null);
  const appealRef = useRef<HTMLTextAreaElement>(null);
  const openSeq = useRef(0);

  async function refreshList() {
    try {
      const data = await apiMyAssignments();
      setItems(data);
      try {
        setPending((await listOutbox()).length);
      } catch {
        /* IndexedDB может быть недоступен */
      }
      try {
        setMyTickets(await apiMyTickets());
      } catch {
        /* ignore for older sessions */
      }
      if (isChief) {
        try {
          setOverview(await apiSiteOverview());
        } catch {
          /* сводка участка недоступна */
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось загрузить список");
    }
  }

  useEffect(() => {
    void refreshList();
  }, []);

  useEffect(() => {
    if (!online) return;
    let cancelled = false;
    (async () => {
      try {
        const flush = await flushOutbox();
        if (cancelled) return;
        if (flush.ok) setInfo(`Отправлено сохранённых офлайн анкет: ${flush.ok}`);
        if (flush.conflicts.length > 0) {
          // Устаревшие черновики удалены из outbox; показываем diff-конфликт.
          const firstConflict = flush.conflicts[0];
          if (firstConflict) {
            setConflictData(firstConflict.response);
          }
        }
        try {
          setPending((await listOutbox()).length);
        } catch {
          /* ignore */
        }
        await refreshList();
      } catch {
        /* сеть/офлайн-очередь не должны блокировать UI */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [online]);

  const stats = useMemo(() => {
    const todo = items.filter((i) => i.evaluation_status !== "submitted").length;
    const done = items.filter((i) => i.evaluation_status === "submitted").length;
    const urgent = items.filter((i) => i.is_urgent && i.evaluation_status !== "submitted").length;
    return { todo, done, urgent, total: items.length };
  }, [items]);

  const filtered = useMemo(() => {
    const query = filter.trim().toLowerCase();
    return items.filter((i) => {
      if (listMode === "todo" && i.evaluation_status === "submitted") return false;
      if (listMode === "done" && i.evaluation_status !== "submitted") return false;
      if (listMode === "urgent" && !(i.is_urgent && i.evaluation_status !== "submitted")) return false;
      if (!query) return true;
      return i.fio.toLowerCase().includes(query) || i.tab_no.toLowerCase().includes(query);
    });
  }, [items, filter, listMode]);

  const avg = useMemo(() => {
    const vals = CRITERIA.map((c) => scores[c.key]);
    return (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1);
  }, [scores]);

  async function openItem(item: AssignmentItem) {
    const seq = ++openSeq.current;
    setSelected(item);
    setScores(emptyScores());
    setComment("");
    setInfo("");
    setError("");
    setShowTicket(false);
    const submitted = item.evaluation_status === "submitted";
    setReadOnly(submitted);
    if (!item.evaluation_id) return;
    setLoadingForm(true);
    try {
      const ev = await apiGetEvaluation(item.evaluation_id);
      if (seq !== openSeq.current) return;
      setScores({
        score_quality: ev.score_quality ?? 3,
        score_discipline: ev.score_discipline ?? 3,
        score_safety: ev.score_safety ?? 3,
        score_skills: ev.score_skills ?? 3,
        score_versatility: ev.score_versatility ?? 3,
      });
      setComment(ev.comment || "");
      setReadOnly(ev.status === "submitted");
      if (ev.status === "submitted" && ev.avg_score != null) {
        setInfo(`Оценка уже отправлена. Средний балл: ${ev.avg_score}`);
      }
    } catch (e) {
      if (seq !== openSeq.current) return;
      setError(e instanceof Error ? e.message : "Не удалось загрузить анкету");
    } finally {
      if (seq === openSeq.current) setLoadingForm(false);
    }
  }

  async function save(submit: boolean) {
    if (!selected || readOnly || busy) return;
    setBusy(true);
    setError("");
    setInfo("");
    const current = selected;
    try {
      const payload = {
        ...scores,
        comment,
        assignment_version: current.assignment_version,
        client_mutation_id:
          typeof crypto !== "undefined" && "randomUUID" in crypto
            ? crypto.randomUUID()
            : `m-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      };
      if (!navigator.onLine) {
        await enqueueOutbox({
          kind: current.is_urgent ? "urgent" : "assignment",
          targetId: current.is_urgent ? current.urgent_request_id! : current.assignment_id,
          submit,
          body: payload,
          createdAt: Date.now(),
        });
        try {
          setPending((await listOutbox()).length);
        } catch {
          /* ignore */
        }
        setInfo("Сохранено без связи. Уйдёт автоматически, когда появится интернет.");
        if (submit) {
          setSelected(null);
          // Не переключаем на «Сданные»: в офлайне статус ещё не submitted
          setListMode("todo");
        }
        return;
      }
      const res = await apiSaveEvaluation(
        current.is_urgent ? "urgent" : "assignment",
        current.is_urgent ? current.urgent_request_id! : current.assignment_id,
        payload,
        submit,
      );
      if (res.conflict) {
        setError(res.conflict_message || "Список изменился — обновите и оцените снова");
        setConflictData(res);
        void refreshList();
        return;
      }
      if (submit) {
        // Сразу выходим из анкеты — не ждём перезагрузку списка (она и «зависала» UI)
        setSelected(null);
        setListMode("done");
        setInfo(`Оценка отправлена. Средний балл: ${res.avg_score}`);
        setBusy(false);
        void refreshList();
        return;
      }
      setInfo(`Черновик сохранён. Средний: ${res.avg_score}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить");
    } finally {
      setBusy(false);
    }
  }

  async function sendTicket(message?: string) {
    const text = (typeof message === "string" ? message : ticketMsg).trim();
    if (!text) return;
    setBusy(true);
    setError("");
    try {
      await apiCreateTicket({
        message: text,
        assignment_id: selected?.assignment_id || null,
        employee_id: selected?.employee_id || null,
      });
      setInfo("Обращение отправлено администратору");
      setTicketMsg("");
      if (appealRef.current) appealRef.current.value = "";
      setShowTicket(false);
      setShowMyTickets(true);
      setMyTickets(await apiMyTickets());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось отправить");
    } finally {
      setBusy(false);
    }
  }

  function submitAppealForm(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const raw = appealRef.current?.value ?? "";
    void sendTicket(raw);
  }

  function onConflictRefill() {
    // Закрываем модалку и перезагружаем актуальную версию назначения.
    setConflictData(null);
    setError("");
    if (!selected) return;
    void apiMyAssignments()
      .then((data) => {
        setItems(data);
        const fresh = data.find((i) => i.assignment_id === selected.assignment_id) || null;
        if (fresh) {
          setSelected(fresh);
          setScores(emptyScores());
          setComment("");
        }
      })
      .catch(() => undefined);
  }

  function onConflictDiscarded() {
    setConflictData(null);
    setError("");
    setSelected(null);
    void refreshList();
  }

  if (selected) {
    const today = new Date().toLocaleDateString("ru-RU");
    return (
      <div className="page anketa-page">
        {conflictData && (
          <ConflictModal
            data={conflictData}
            onRefill={onConflictRefill}
            onDiscarded={onConflictDiscarded}
          />
        )}
        <header className="top">
          <button className="link" type="button" onClick={() => setSelected(null)}>
            ← К списку
          </button>
          <span className={`pill ${online ? "ok" : "warn"}`}>{online ? "Есть связь" : "Без связи"}</span>
        </header>

        <section className="anketa panel">
          <h1 className="anketa-title">{anketaTitle(user.role)}</h1>

          <div className="anketa-meta">
            <div>
              <div className="meta-label">Сотрудник (кого оценивают)</div>
              <div className="meta-value">{selected.fio}</div>
              <div className="muted">Таб. № {selected.tab_no}</div>
              <div className="muted">
                Должность: {selected.position_1c || selected.position_fact || "—"}
              </div>
              <div className="muted">
                Факт. должность: {selected.position_fact || "—"}
              </div>
              <div className="muted">Участок: {selected.site_name || "—"}</div>
              {selected.hire_date && <div className="muted">Дата приёма: {selected.hire_date}</div>}
              {selected.experience_text && <div className="muted">Стаж: {selected.experience_text}</div>}
              {isChief && selected.hourly_rate != null && (
                <div className="muted">
                  ЧТС:{" "}
                  <strong
                    className={selected.is_rate_expired ? "rate-expired" : undefined}
                    title={
                      selected.is_rate_expired
                        ? "ЧТС не повышалась более 6 месяцев!"
                        : undefined
                    }
                  >
                    {selected.hourly_rate} ₽/ч
                  </strong>
                  {selected.is_rate_expired && (
                    <span className="rate-expired" title="ЧТС не повышалась более 6 месяцев!">
                      {" "}⚠
                    </span>
                  )}
                  {selected.rate_last_raised
                    ? ` · поднятие ${selected.rate_last_raised}`
                    : selected.rate_updated_at
                      ? ` · изм. ${selected.rate_updated_at}`
                      : ""}
                </div>
              )}
              {selected.last_final_score != null && (
                <div className="muted">Прошлый итог: {selected.last_final_score}</div>
              )}
            </div>
            <div>
              <div className="meta-label">Кто оценивает</div>
              <div className="meta-value">{user.fio}</div>
              <div className="muted">{roleRu(user.role)} · таб. {user.tab_no}</div>
              <div className="muted">Дата оценки: {today}</div>
              {selected.is_urgent && !readOnly && <div className="pill danger">Срочная оценка</div>}
              {readOnly && <div className="pill ok">Отправлено</div>}
              <div className="muted">
                Роль в закреплении:{" "}
                {selected.my_role === "secondary" ? "второй оценщик" : "основной оценщик"}
              </div>
            </div>
          </div>

          {loadingForm && <p className="muted">Загрузка сохранённых баллов…</p>}

          <p className="anketa-intro">
            Оцените, пожалуйста, согласно предложенным индикаторам по пятибалльной шкале, который, по вашему
            мнению, наиболее соответствует уровню сотрудника.
          </p>

          <div className="scale-box">
            <div className="scale-head">
              <strong>Уровень / балл</strong>
              <strong>Описание уровня</strong>
            </div>
            {SCALE.map((s) => (
              <div key={s.n} className="scale-row">
                <span>
                  {s.n} — {s.title}
                </span>
                <span className="muted">{s.hint}</span>
              </div>
            ))}
          </div>

          <div className="anketa-avg">
            Средний балл: <strong>{avg}</strong>
          </div>

          {isChief && readOnly && (
            <div className="anketa-combined">
              {selected.combined_score != null ? (
                <>
                  Общая оценка (с учётом 1-го оценщика): <strong>{selected.combined_score}</strong>
                  <div className="muted" style={{ fontSize: "0.8rem" }}>
                    Баллы первого оценщика не отображаются
                  </div>
                </>
              ) : (
                <span className="muted">
                  1-й оценщик ещё не сдал анкету — общая оценка появится после его сдачи.
                </span>
              )}
            </div>
          )}

          <div className="criteria-list">
            <div className="criteria-head">
              <span>Общие параметры</span>
              <span>Оценка</span>
            </div>
            {CRITERIA.map((c, idx) => (
              <div key={c.key} className="criteria-item">
                <div className="criteria-text">
                  <strong>
                    {idx + 1}. {c.title}
                  </strong>
                  <p className="muted">{c.desc}</p>
                </div>
                <div className="score-pills" role="group" aria-label={c.title}>
                  {[1, 2, 3, 4, 5].map((n) => (
                    <button
                      key={n}
                      type="button"
                      disabled={readOnly || loadingForm || busy}
                      className={scores[c.key] === n ? "score-pill active" : "score-pill"}
                      onClick={() => setScores({ ...scores, [c.key]: n })}
                    >
                      {n}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <label>
            Рекомендации / комментарии
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={3}
              disabled={readOnly || loadingForm || busy}
              readOnly={readOnly}
            />
          </label>

          {error && <p className="error">{error}</p>}
          {info && <p className="ok-text">{info}</p>}

          {!readOnly && (
            <div className="actions">
              <button type="button" disabled={busy || loadingForm} onClick={() => save(false)}>
                Черновик
              </button>
              <button type="button" className="primary" disabled={busy || loadingForm} onClick={() => save(true)}>
                Отправить оценку
              </button>
            </div>
          )}
          {readOnly && (
            <p className="muted" style={{ marginTop: "0.5rem" }}>
              Анкета уже отправлена. Изменить баллы нельзя — при ошибке напишите обращение администратору.
            </p>
          )}

          <p className="muted" style={{ marginTop: "0.75rem" }}>
            Непосредственный руководитель: {user.fio}
          </p>

          <button className="link" type="button" onClick={() => setShowTicket((v) => !v)}>
            Сообщить об ошибке в списке
          </button>
          {showTicket && (
            <div className="ticket-box">
              <textarea
                placeholder="Например: человек не на этой площадке / лишний в списке"
                value={ticketMsg}
                onChange={(e) => setTicketMsg(e.target.value)}
                rows={3}
              />
              <button type="button" disabled={busy} onClick={() => sendTicket()}>
                Отправить администратору
              </button>
            </div>
          )}
        </section>
      </div>
    );
  }

  return (
    <div className="page narrow">
      {conflictData && (
        <ConflictModal
          data={conflictData}
          onRefill={onConflictRefill}
          onDiscarded={onConflictDiscarded}
        />
      )}
      <header className="top">
        <div>
          <p className="brand">{roleRu(user.role)} · мой список</p>
          <h1>{user.fio}</h1>
          <p className="muted">
            {isChief
              ? `Участок: ${user.site_name || "—"}. Нажмите на сотрудника, чтобы поставить оценку`
              : "Нажмите на сотрудника, чтобы поставить оценку"}
          </p>
        </div>
        <div className="right">
          <span className={`pill ${online ? "ok" : "warn"}`}>{online ? "Сеть" : "Офлайн"}</span>
          {pending > 0 && <span className="pill warn">Ждут отправки: {pending}</span>}
        </div>
      </header>

      {isChief && overview && (
        <section className="panel chief-overview">
          <button type="button" className="link" onClick={() => setShowOverview((v) => !v)}>
            {showOverview ? "▾ Сводка по участку" : "▸ Сводка по участку"}
          </button>
          {showOverview && (
            <>
              {overview.warning && <p className="error">{overview.warning}</p>}
              <div className="chief-overview-meta">
                <span>
                  Период: <strong>{overview.period_code}</strong>
                </span>
                <span>
                  Начало оценки:{" "}
                  <strong>{overview.evaluation_started_on || overview.period_starts_on || "—"}</strong>
                </span>
                <span>
                  Тарифная сетка:{" "}
                  <strong>
                    {overview.tariff_min != null && overview.tariff_max != null
                      ? `${overview.tariff_min} — ${overview.tariff_max} ₽/ч`
                      : "—"}
                  </strong>
                </span>
              </div>
              {overview.masters.length > 0 ? (
                <div className="excel-wrap">
                  <table className="excel-table">
                    <thead>
                      <tr>
                        <th>Прораб / мастер</th>
                        <th>На оценке</th>
                        <th>Оценено</th>
                        <th>Осталось</th>
                      </tr>
                    </thead>
                    <tbody>
                      {overview.masters.map((m) => (
                        <tr key={m.user_id}>
                          <td>
                            {m.fio} <span className="muted">({m.role === "master" ? "мастер" : "прораб"})</span>
                          </td>
                          <td>{m.total}</td>
                          <td>{m.submitted}</td>
                          <td>{m.remaining}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="muted">На вашем участке пока нет прорабов/мастеров с назначенными людьми.</p>
              )}
            </>
          )}
        </section>
      )}

      {isChief && onOpenRegistry && (
        <button type="button" className="primary" style={{ width: "100%", marginBottom: "0.75rem" }} onClick={onOpenRegistry}>
          Реестр оценок участка →
        </button>
      )}

      <section className="field-summary">
        <button type="button" className={`metric warn clickable ${listMode === "todo" ? "metric-active" : ""}`} onClick={() => setListMode("todo")}>
          <div className="metric-ico" aria-hidden>⏳</div>
          <div className="label">Осталось</div>
          <div className="value">{stats.todo}</div>
        </button>
        <button type="button" className={`metric ok clickable ${listMode === "done" ? "metric-active" : ""}`} onClick={() => setListMode("done")}>
          <div className="metric-ico" aria-hidden>✅</div>
          <div className="label">Готово</div>
          <div className="value">{stats.done}</div>
        </button>
        <button type="button" className={`metric clickable ${stats.urgent ? "danger" : ""} ${listMode === "urgent" ? "metric-active" : ""}`} onClick={() => setListMode("urgent")}>
          <div className="metric-ico" aria-hidden>⚡</div>
          <div className="label">Срочно</div>
          <div className="value">{stats.urgent}</div>
        </button>
      </section>

      <button className="link" type="button" onClick={() => setShowMyTickets((v) => !v)}>
        {showMyTickets ? "Скрыть мои обращения" : `Мои обращения${myTickets.some((t) => t.admin_note) ? " · есть ответы" : ""}`}
      </button>
      {showMyTickets && (
        <div className="panel" style={{ marginBottom: "0.75rem" }}>
          <form className="appeal-form" onSubmit={submitAppealForm}>
            <label htmlFor="appeal-text">
              Новое обращение администратору
              <textarea
                id="appeal-text"
                ref={appealRef}
                name="appeal"
                defaultValue=""
                placeholder="Опишите проблему: ошибка в списке, другой человек, вопрос…"
                rows={4}
                autoComplete="off"
                enterKeyHint="send"
              />
            </label>
            <button type="submit" className="primary" disabled={busy}>
              Отправить обращение
            </button>
          </form>
          {myTickets.length === 0 && <p className="muted">Вы ещё не отправляли обращений</p>}
          {myTickets.map((t) => (
            <div key={t.id} className="ticket-card" style={{ marginBottom: "0.5rem" }}>
              <div className="muted">№{t.id} · {t.status === "done" ? "закрыто" : "открыто"}</div>
              <div>{t.message}</div>
              {t.admin_note ? (
                <p className="ok-text"><strong>Ответ администрации:</strong> {t.admin_note}</p>
              ) : (
                <p className="muted">Ответа пока нет</p>
              )}
            </div>
          ))}
        </div>
      )}

      <input
        className="search"
        placeholder="Найти по ФИО или табельному"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      />

      {error && <p className="error">{error}</p>}
      {info && <p className="ok-text">{info}</p>}

      <div className="list">
        {filtered.length === 0 && (
          <div className="panel">
            <p className="muted">
              {items.length === 0
                ? "Пока нет людей для оценки. Администратор должен закрепить вас и нажать «Отправить для оценки»."
                : listMode === "done"
                  ? "Пока нет отправленных анкет."
                  : listMode === "urgent"
                    ? "Нет открытых срочных задач."
                    : "Все оценки в этом списке уже отправлены. Нажмите «Готово», чтобы посмотреть сданные."}
            </p>
          </div>
        )}
        {filtered.map((item) => (
          <button
            key={`${item.is_urgent ? "u" : "a"}-${item.assignment_id}-${item.urgent_request_id}-${item.employee_id}`}
            className="list-item"
            type="button"
            onClick={() => void openItem(item)}
          >
            <div>
              <strong>{item.fio}</strong>
              <p className="muted">
                {item.tab_no} · {item.site_name || item.site_code || "площадка —"}
              </p>
              {isChief && item.hourly_rate != null && (
                <p className="muted" style={{ margin: 0 }}>
                  ЧТС:{" "}
                  <span
                    className={item.is_rate_expired ? "rate-expired" : undefined}
                    title={
                      item.is_rate_expired ? "ЧТС не повышалась более 6 месяцев!" : undefined
                    }
                  >
                    {item.hourly_rate} ₽/ч
                  </span>
                  {item.is_rate_expired && (
                    <span className="rate-expired" title="ЧТС не повышалась более 6 месяцев!">
                      {" "}⚠
                    </span>
                  )}
                  {item.rate_last_raised
                    ? ` · поднятие ${item.rate_last_raised}`
                    : item.rate_updated_at
                      ? ` · изм. ${item.rate_updated_at}`
                      : ""}
                </p>
              )}
            </div>
            <div className="badges">
              {item.is_urgent && item.evaluation_status !== "submitted" && (
                <span className="pill danger">Срочно</span>
              )}
              {isChief && item.combined_score != null && (
                <span className="pill ok" title="Общая оценка с учётом 1-го оценщика">
                  Общая: {item.combined_score}
                </span>
              )}
              {isChief &&
                item.my_role === "secondary" &&
                item.evaluation_status === "submitted" &&
                item.combined_score == null &&
                !item.peer_submitted && (
                  <span className="pill info" title="1-й оценщик ещё не сдал анкету">
                    Ждём 1-го
                  </span>
                )}
              <span
                className={`pill ${item.evaluation_status === "submitted" ? "ok" : item.evaluation_status === "draft" ? "info" : "warn"
                  }`}
              >
                {statusRu(item.evaluation_status, false)}
              </span>
            </div>
          </button>
        ))}
      </div>

      <nav className="bottom-nav" aria-label="Действия">
        <button type="button" className={listMode === "todo" ? "active" : ""} onClick={() => setListMode("todo")}>
          <span className="ico">⏳</span>
          К оценке
        </button>
        <button type="button" className={listMode === "done" ? "active" : ""} onClick={() => setListMode("done")}>
          <span className="ico">✓</span>
          Сданные
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            setInfo("");
            setError("");
            void refreshList().then(() => setInfo("Список обновлён"));
          }}
          title="Обновить список с сервера"
        >
          <span className="ico">↻</span>
          Обновить
        </button>
        <button
          type="button"
          className={showMyTickets ? "active" : ""}
          onClick={() => setShowMyTickets((v) => !v)}
        >
          <span className="ico">✉</span>
          Обращения
        </button>
        <NotificationBell variant="nav" />
        <button type="button" onClick={onLogout}>
          <span className="ico">⎋</span>
          Выйти
        </button>
      </nav>
    </div>
  );
}
