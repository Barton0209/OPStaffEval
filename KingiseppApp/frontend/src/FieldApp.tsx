import { useEffect, useMemo, useRef, useState } from "react";
import {
  apiCreateTicket,
  apiMyAssignments,
  apiMyTickets,
  apiSaveEvaluation,
  type AssignmentItem,
  type SessionUser,
  type Ticket,
} from "./api";
import { enqueueOutbox, flushOutbox, listOutbox } from "./offline";

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
  return role;
}

function anketaTitle(role: string) {
  if (role === "foreman") return "Анкета по оценке деятельности рабочего персонала (Производитель работ)";
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
};

export function FieldApp({ user, online, onLogout }: Props) {
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
  const [onlyTodo, setOnlyTodo] = useState(true);
  const [listMode, setListMode] = useState<"todo" | "done" | "urgent" | "all">("todo");
  const [myTickets, setMyTickets] = useState<Ticket[]>([]);
  const [showMyTickets, setShowMyTickets] = useState(true);
  const appealRef = useRef<HTMLTextAreaElement>(null);

  async function refreshList() {
    try {
      const data = await apiMyAssignments();
      setItems(data);
      setPending((await listOutbox()).length);
      try {
        setMyTickets(await apiMyTickets());
      } catch {
        /* ignore for older sessions */
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось загрузить список");
    }
  }

  useEffect(() => {
    refreshList();
  }, []);

  useEffect(() => {
    if (!online) return;
    (async () => {
      const n = await flushOutbox();
      if (n) setInfo(`Отправлено сохранённых офлайн анкет: ${n}`);
      setPending((await listOutbox()).length);
      await refreshList();
    })();
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
      if (onlyTodo && listMode === "all" && i.evaluation_status === "submitted") return false;
      if (!query) return true;
      return i.fio.toLowerCase().includes(query) || i.tab_no.toLowerCase().includes(query);
    });
  }, [items, filter, onlyTodo, listMode]);

  const avg = useMemo(() => {
    const vals = CRITERIA.map((c) => scores[c.key]);
    return (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1);
  }, [scores]);

  function openItem(item: AssignmentItem) {
    setSelected(item);
    setScores(emptyScores());
    setComment("");
    setInfo("");
    setError("");
    setShowTicket(false);
  }

  async function save(submit: boolean) {
    if (!selected) return;
    setBusy(true);
    setError("");
    setInfo("");
    const payload = {
      ...scores,
      comment,
      assignment_version: selected.assignment_version,
      client_mutation_id: crypto.randomUUID(),
    };
    try {
      if (!navigator.onLine) {
        await enqueueOutbox({
          kind: selected.is_urgent ? "urgent" : "assignment",
          targetId: selected.is_urgent ? selected.urgent_request_id! : selected.assignment_id,
          submit,
          body: payload,
          createdAt: Date.now(),
        });
        setPending((await listOutbox()).length);
        setInfo("Сохранено без связи. Уйдёт автоматически, когда появится интернет.");
        if (submit) setSelected(null);
        return;
      }
      const res = await apiSaveEvaluation(
        selected.is_urgent ? "urgent" : "assignment",
        selected.is_urgent ? selected.urgent_request_id! : selected.assignment_id,
        payload,
        submit,
      );
      if (res.conflict) {
        setError(res.conflict_message || "Список изменился — обновите и оцените снова");
        await refreshList();
        return;
      }
      setInfo(submit ? `Оценка отправлена. Средний балл: ${res.avg_score}` : `Черновик сохранён. Средний: ${res.avg_score}`);
      if (submit) {
        setSelected(null);
        await refreshList();
      }
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

  if (selected) {
    const today = new Date().toLocaleDateString("ru-RU");
    return (
      <div className="page anketa-page">
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
              {selected.last_final_score != null && (
                <div className="muted">Прошлый итог: {selected.last_final_score}</div>
              )}
            </div>
            <div>
              <div className="meta-label">Кто оценивает</div>
              <div className="meta-value">{user.fio}</div>
              <div className="muted">{roleRu(user.role)} · таб. {user.tab_no}</div>
              <div className="muted">Дата оценки: {today}</div>
              {selected.is_urgent && <div className="pill danger">Срочная оценка</div>}
              <div className="muted">
                Роль в закреплении:{" "}
                {selected.my_role === "secondary" ? "второй оценщик" : "основной оценщик"}
              </div>
            </div>
          </div>

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
            <textarea value={comment} onChange={(e) => setComment(e.target.value)} rows={3} />
          </label>

          {error && <p className="error">{error}</p>}
          {info && <p className="ok-text">{info}</p>}

          <div className="actions">
            <button type="button" disabled={busy} onClick={() => save(false)}>
              Черновик
            </button>
            <button type="button" className="primary" disabled={busy} onClick={() => save(true)}>
              Отправить оценку
            </button>
          </div>

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
      <header className="top">
        <div>
          <p className="brand">{roleRu(user.role)} · мой список</p>
          <h1>{user.fio}</h1>
          <p className="muted">Нажмите на сотрудника, чтобы поставить оценку</p>
        </div>
        <div className="right">
          <span className={`pill ${online ? "ok" : "warn"}`}>{online ? "Сеть" : "Офлайн"}</span>
          {pending > 0 && <span className="pill warn">Ждут отправки: {pending}</span>}
        </div>
      </header>

      <section className="field-summary">
        <button type="button" className={`metric warn clickable ${listMode === "todo" ? "metric-active" : ""}`} onClick={() => { setListMode("todo"); setOnlyTodo(true); }}>
          <div className="metric-ico" aria-hidden>⏳</div>
          <div className="label">Осталось</div>
          <div className="value">{stats.todo}</div>
        </button>
        <button type="button" className={`metric ok clickable ${listMode === "done" ? "metric-active" : ""}`} onClick={() => { setListMode("done"); setOnlyTodo(false); }}>
          <div className="metric-ico" aria-hidden>✅</div>
          <div className="label">Готово</div>
          <div className="value">{stats.done}</div>
        </button>
        <button type="button" className={`metric clickable ${stats.urgent ? "danger" : ""} ${listMode === "urgent" ? "metric-active" : ""}`} onClick={() => { setListMode("urgent"); setOnlyTodo(false); }}>
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
      <label className="check" style={{ marginBottom: "0.75rem" }}>
        <input type="checkbox" checked={onlyTodo} onChange={(e) => setOnlyTodo(e.target.checked)} />
        показывать только не оценённых
      </label>

      {error && <p className="error">{error}</p>}
      {info && <p className="ok-text">{info}</p>}

      <div className="list">
        {filtered.length === 0 && (
          <div className="panel">
            <p className="muted">
              {items.length === 0
                ? "Пока нет людей для оценки. Администратор должен назначить вас основным оценщиком или выдать срочную заявку."
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
            onClick={() => openItem(item)}
          >
            <div>
              <strong>{item.fio}</strong>
              <p className="muted">
                {item.tab_no} · {item.site_name || item.site_code || "площадка —"}
              </p>
            </div>
            <div className="badges">
              {item.is_urgent && <span className="pill danger">Срочно</span>}
              <span
                className={`pill ${
                  item.evaluation_status === "submitted" ? "ok" : item.evaluation_status === "draft" ? "info" : "warn"
                }`}
              >
                {statusRu(item.evaluation_status, false)}
              </span>
            </div>
          </button>
        ))}
      </div>

      <nav className="bottom-nav" aria-label="Действия">
        <button type="button" className="active" onClick={() => refreshList()}>
          <span className="ico">☰</span>
          Список
        </button>
        <button type="button" onClick={() => setOnlyTodo((v) => !v)}>
          <span className="ico">{onlyTodo ? "✓" : "◎"}</span>
          {onlyTodo ? "Только новые" : "Все"}
        </button>
        <button type="button" onClick={onLogout}>
          <span className="ico">⎋</span>
          Выйти
        </button>
      </nav>
    </div>
  );
}
