import { useEffect, useMemo, useState } from "react";
import {
  apiAdminAssignments,
  apiCloseUrgent,
  apiCreateDelegation,
  apiCreateEmployee,
  apiCreateUrgent,
  apiDashboard,
  apiDeactivateDelegation,
  apiDelegations,
  apiEmployees,
  apiEscalations,
  apiEvents,
  apiFormalizeCandidate,
  apiImportAll,
  apiImportUpload,
  apiListUrgent,
  apiPatchAssignment,
  apiPatchTicket,
  apiTickets,
  apiUsers,
  type AdminAssignment,
  type AdminEmployee,
  type AdminUser,
  type Dashboard,
  type SessionUser,
  type Ticket,
} from "./api";
import { BrandHeader } from "./BrandHeader";

type Tab =
  | "dash"
  | "assign"
  | "urgent"
  | "delegate"
  | "employees"
  | "tickets"
  | "events"
  | "import";

type Props = {
  user: SessionUser;
  onLogout: () => void;
  onOpenRegistry: () => void;
};

const TABS: { id: Tab; label: string }[] = [
  { id: "dash", label: "Сводка" },
  { id: "assign", label: "Назначения" },
  { id: "urgent", label: "Срочная" },
  { id: "delegate", label: "Замещение" },
  { id: "employees", label: "База" },
  { id: "tickets", label: "Обращения" },
  { id: "events", label: "Журнал" },
  { id: "import", label: "Импорт Excel" },
];

function pct(part: number, total: number) {
  if (!total) return 0;
  return Math.round((part / total) * 100);
}

export function AdminApp({ user, onLogout, onOpenRegistry }: Props) {
  const [tab, setTab] = useState<Tab>("dash");
  const [dash, setDash] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);

  const [assignments, setAssignments] = useState<AdminAssignment[]>([]);
  const [assignQ, setAssignQ] = useState("");
  const [awaitingOnly, setAwaitingOnly] = useState(false);
  const [filterSite, setFilterSite] = useState("");
  const [filterMaster, setFilterMaster] = useState("");
  const [masters, setMasters] = useState<AdminUser[]>([]);

  const [urgent, setUrgent] = useState<
    { id: number; fio: string; tab_no: string; status: string; comment: string | null; employee_id: number }[]
  >([]);
  const [urgEmpId, setUrgEmpId] = useState("");
  const [urgEmpQ, setUrgEmpQ] = useState("");
  const [urgEvalIds, setUrgEvalIds] = useState<number[]>([]);
  const [replyDrafts, setReplyDrafts] = useState<Record<number, string>>({});

  const [delegations, setDelegations] = useState<
    {
      id: number;
      original_user_id: number;
      substitute_user_id: number;
      starts_on: string;
      ends_on: string;
      reason: string | null;
      is_active: boolean;
    }[]
  >([]);
  const [delOrig, setDelOrig] = useState("");
  const [delSub, setDelSub] = useState("");
  const [delFrom, setDelFrom] = useState("");
  const [delTo, setDelTo] = useState("");

  const [employees, setEmployees] = useState<AdminEmployee[]>([]);
  const [empQ, setEmpQ] = useState("");
  const [candOnly, setCandOnly] = useState(false);
  const [newTab, setNewTab] = useState("");
  const [newFio, setNewFio] = useState("");
  const [formalizeId, setFormalizeId] = useState("");
  const [formalizeTab, setFormalizeTab] = useState("");

  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [events, setEvents] = useState<
    { id: number; entity_type: string; entity_id: number | null; action: string; created_at: string | null }[]
  >([]);
  const [escalations, setEscalations] = useState<
    {
      user_id: number;
      fio: string;
      tab_no: string;
      pending_assignments: number;
      submitted: number;
      last_login_at: string | null;
    }[]
  >([]);

  const [filterMode, setFilterMode] = useState<"all" | "evaluate" | "with_primary" | "awaiting" | "dual">("all");
  const [fileBase, setFileBase] = useState<File | null>(null);
  const [fileUsers, setFileUsers] = useState<File | null>(null);
  const [fileCarnet, setFileCarnet] = useState<File | null>(null);

  async function loadDash() {
    setDash(await apiDashboard());
    setEscalations(await apiEscalations());
  }

  useEffect(() => {
    (async () => {
      try {
        await loadDash();
        const [m, f] = await Promise.all([apiUsers("master"), apiUsers("foreman")]);
        setMasters([...m, ...f]);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Ошибка загрузки");
      }
    })();
  }, []);

  useEffect(() => {
    (async () => {
      setError("");
      try {
        if (tab === "dash") await loadDash();
        if (tab === "assign") {
          setAssignments(await apiAdminAssignments({ q: assignQ || undefined, awaiting: awaitingOnly }));
        }
        if (tab === "urgent") {
          setUrgent(await apiListUrgent());
          setEmployees(await apiEmployees({}));
        }
        if (tab === "delegate") setDelegations(await apiDelegations());
        if (tab === "employees") {
          setEmployees(await apiEmployees({ q: empQ || undefined, candidates: candOnly }));
        }
        if (tab === "tickets") setTickets(await apiTickets());
        if (tab === "events") setEvents(await apiEvents(80));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Ошибка загрузки");
      }
    })();
  }, [tab, awaitingOnly, candOnly]);

  const progress = useMemo(() => {
    if (!dash) return 0;
    return pct(dash.submitted_evaluations, dash.evaluate_yes || 1);
  }, [dash]);

  const sites = useMemo(() => {
    const s = new Set<string>();
    for (const a of assignments) if (a.site_name) s.add(a.site_name);
    return [...s].sort();
  }, [assignments]);

  const filteredAssignments = useMemo(() => {
    return assignments.filter((a) => {
      if (filterSite && a.site_name !== filterSite) return false;
      if (filterMaster && String(a.primary_user_id) !== filterMaster) return false;
      if (filterMode === "evaluate" && !a.evaluate) return false;
      if (filterMode === "with_primary" && !a.primary_user_id) return false;
      if (filterMode === "awaiting" && a.primary_user_id) return false;
      if (filterMode === "dual" && !a.dual_enabled) return false;
      return true;
    });
  }, [assignments, filterSite, filterMaster, filterMode]);

  function go(tabId: Tab, opts?: { awaiting?: boolean; candidates?: boolean; mode?: typeof filterMode }) {
    if (opts?.awaiting != null) setAwaitingOnly(opts.awaiting);
    if (opts?.candidates != null) setCandOnly(opts.candidates);
    if (opts?.mode) setFilterMode(opts.mode);
    setTab(tabId);
    setInfo("");
    setError("");
  }

  async function runImportFolder() {
    setBusy(true);
    setInfo("");
    try {
      const res = await apiImportAll();
      setInfo(
        res
          .map((r) => `${r.source}: добавлено ${r.added}, обновлено ${r.updated}, пропущено ${r.skipped}`)
          .join(" · "),
      );
      await loadDash();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Импорт не удался");
    } finally {
      setBusy(false);
    }
  }

  async function runImportUpload() {
    setBusy(true);
    setInfo("");
    setError("");
    try {
      const res = await apiImportUpload({ base: fileBase, users: fileUsers, carnet: fileCarnet });
      setInfo(
        res
          .map((r) => `${r.source}: добавлено ${r.added}, обновлено ${r.updated}, пропущено ${r.skipped}`)
          .join(" · "),
      );
      setFileBase(null);
      setFileUsers(null);
      setFileCarnet(null);
      await loadDash();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Загрузка не удалась");
    } finally {
      setBusy(false);
    }
  }

  async function setPrimary(asg: AdminAssignment, primaryId: number) {
    setBusy(true);
    try {
      await apiPatchAssignment(asg.assignment_id, { primary_user_id: primaryId, evaluate: true });
      setInfo(`Назначен основной оценщик для ${asg.fio}`);
      setAssignments(await apiAdminAssignments({ q: assignQ || undefined, awaiting: awaitingOnly }));
      await loadDash();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось назначить");
    } finally {
      setBusy(false);
    }
  }

  async function toggleDual(asg: AdminAssignment, dual: boolean, secondaryId?: number) {
    setBusy(true);
    try {
      await apiPatchAssignment(asg.assignment_id, {
        dual_enabled: dual,
        secondary_user_id: dual ? secondaryId || null : null,
      });
      setAssignments(await apiAdminAssignments({ q: assignQ || undefined, awaiting: awaitingOnly }));
      setInfo(dual ? "Включена двойная оценка" : "Двойная оценка отключена");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка настройки второго оценщика");
    } finally {
      setBusy(false);
    }
  }

  function masterName(id: number) {
    return masters.find((m) => m.id === id)?.fio || `№${id}`;
  }

  return (
    <div className="page excel-page">
      <BrandHeader
        title="Отдел мобилизации и координации ОП Кингисепп"
        subtitle={`${user.fio} · система оценки персонала`}
        right={
          <>
            <button type="button" onClick={onOpenRegistry}>
              Реестр
            </button>
            <button className="ghost" type="button" onClick={onLogout}>
              Выйти
            </button>
          </>
        }
      />

      <nav className="tabs" aria-label="Разделы">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={tab === t.id ? "tab active" : "tab"}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {error && <p className="error">{error}</p>}
      {info && <p className="ok-text">{info}</p>}

      {tab === "dash" && dash && (
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
            <button type="button" className="metric info clickable" onClick={() => go("assign", { awaiting: false, mode: "all" })}>
              <div className="metric-ico" aria-hidden>📋</div>
              <div className="label">В реестре закреплений</div>
              <div className="value">{dash.total_assignments}</div>
              <div className="hint">открыть таблицу назначений</div>
            </button>
            <button type="button" className="metric ok clickable" onClick={() => go("assign", { awaiting: false, mode: "evaluate" })}>
              <div className="metric-ico" aria-hidden>✅</div>
              <div className="label">Идут на оценку</div>
              <div className="value">{dash.evaluate_yes}</div>
              <div className="hint">только отмеченные к оценке</div>
            </button>
            <button type="button" className="metric clickable" onClick={() => go("assign", { awaiting: false, mode: "with_primary" })}>
              <div className="metric-ico" aria-hidden>👤</div>
              <div className="label">Есть основной оценщик</div>
              <div className="value">{dash.with_primary}</div>
              <div className="hint">с назначенным мастером/ПР</div>
            </button>
            <button type="button" className={`metric clickable ${dash.awaiting_primary ? "warn" : ""}`} onClick={() => go("assign", { awaiting: true, mode: "awaiting" })}>
              <div className="metric-ico" aria-hidden>⏳</div>
              <div className="label">Ждут назначения</div>
              <div className="value">{dash.awaiting_primary}</div>
              <div className="hint">без оценщика — назначить</div>
            </button>
            <button type="button" className={`metric clickable ${dash.candidates ? "info" : ""}`} onClick={() => go("employees", { candidates: true })}>
              <div className="metric-ico" aria-hidden>🆕</div>
              <div className="label">Кандидаты</div>
              <div className="value">{dash.candidates}</div>
              <div className="hint">открыть базу кандидатов</div>
            </button>
            <button type="button" className="metric clickable" onClick={() => go("assign", { awaiting: false, mode: "dual" })}>
              <div className="metric-ico" aria-hidden>👥</div>
              <div className="label">Двойная оценка</div>
              <div className="value">{dash.dual_enabled}</div>
              <div className="hint">два независимых оценщика</div>
            </button>
            <button type="button" className={`metric clickable ${dash.open_urgent ? "warn" : "ok"}`} onClick={() => go("urgent")}>
              <div className="metric-ico" aria-hidden>⚡</div>
              <div className="label">Срочные оценки</div>
              <div className="value">{dash.open_urgent}</div>
              <div className="hint">открытые срочные запросы</div>
            </button>
            <button type="button" className={`metric clickable ${dash.open_tickets ? "warn" : "ok"}`} onClick={() => go("tickets")}>
              <div className="metric-ico" aria-hidden>💬</div>
              <div className="label">Обращения с площадки</div>
              <div className="value">{dash.open_tickets}</div>
              <div className="hint">ошибки в списках</div>
            </button>
            <button type="button" className={`metric clickable ${dash.escalations ? "danger" : "ok"}`} onClick={() => document.getElementById("escalations-block")?.scrollIntoView({ behavior: "smooth" })}>
              <div className="metric-ico" aria-hidden>🚨</div>
              <div className="label">Эскалации</div>
              <div className="value">{dash.escalations}</div>
              <div className="hint">нет входа &gt; 3 дней</div>
            </button>
            <button type="button" className="metric ok clickable" onClick={() => onOpenRegistry()}>
              <div className="metric-ico" aria-hidden>📊</div>
              <div className="label">Сдано анкет</div>
              <div className="value">{dash.submitted_evaluations}</div>
              <div className="hint">открыть реестр итогов</div>
            </button>
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
      )}

      {tab === "assign" && (
        <section className="panel excel-panel">
          <h2>Назначения оценщиков</h2>
          <p className="muted">Таблица как в Excel: фильтры сверху, прокрутка по горизонтали и вертикали.</p>
          <div className="excel-toolbar">
            <input
              placeholder="Фильтр: ФИО или табельный"
              value={assignQ}
              onChange={(e) => setAssignQ(e.target.value)}
            />
            <button
              type="button"
              onClick={async () =>
                setAssignments(await apiAdminAssignments({ q: assignQ || undefined, awaiting: awaitingOnly }))
              }
            >
              Применить
            </button>
            <select value={filterSite} onChange={(e) => setFilterSite(e.target.value)}>
              <option value="">Все площадки</option>
              {sites.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
            <select value={filterMaster} onChange={(e) => setFilterMaster(e.target.value)}>
              <option value="">Все мастера / прорабы</option>
              {masters.map((m) => (
                <option key={m.id} value={String(m.id)}>
                  {m.fio} · {m.role === "master" ? "мастер" : "прораб"}
                </option>
              ))}
            </select>
            <label className="check">
              <input
                type="checkbox"
                checked={awaitingOnly}
                onChange={(e) => setAwaitingOnly(e.target.checked)}
              />
              только без оценщика
            </label>
            <select value={filterMode} onChange={(e) => setFilterMode(e.target.value as typeof filterMode)}>
              <option value="all">все строки</option>
              <option value="evaluate">к оценке</option>
              <option value="with_primary">с оценщиком</option>
              <option value="awaiting">ждут назначения</option>
              <option value="dual">двойная оценка</option>
            </select>
            <span className="muted">Строк: {filteredAssignments.length}</span>
          </div>
          <div className="excel-wrap tall">
            <table className="excel-table sticky">
              <thead>
                <tr>
                  <th className="sticky-col">№</th>
                  <th className="sticky-col-2">Таб. №</th>
                  <th>ФИО сотрудника</th>
                  <th>Площадка</th>
                  <th>К оценке</th>
                  <th>Основной оценщик</th>
                  <th>Второй оценщик</th>
                  <th>Версия</th>
                </tr>
              </thead>
              <tbody>
                {filteredAssignments.map((a, idx) => (
                  <tr key={a.assignment_id} className={!a.primary_user_id ? "row-warn" : undefined}>
                    <td className="sticky-col">{idx + 1}</td>
                    <td className="sticky-col-2">{a.tab_no}</td>
                    <td>
                      {a.fio}
                      {a.is_candidate ? " (кандидат)" : ""}
                    </td>
                    <td>{a.site_name || "—"}</td>
                    <td>{a.evaluate ? "да" : "нет"}</td>
                    <td>
                      {a.primary_fio || (
                        <select
                          disabled={busy}
                          defaultValue=""
                          onChange={(e) => {
                            const id = Number(e.target.value);
                            if (id) setPrimary(a, id);
                          }}
                        >
                          <option value="">Назначить…</option>
                          {masters.map((m) => (
                            <option key={m.id} value={m.id}>
                              {m.fio} · {m.role === "master" ? "мастер" : "прораб"}
                            </option>
                          ))}
                        </select>
                      )}
                    </td>
                    <td>
                      {a.dual_enabled ? (
                        <button type="button" disabled={busy} onClick={() => toggleDual(a, false)}>
                          Отключить
                        </button>
                      ) : (
                        <select
                          disabled={busy || !a.primary_user_id}
                          defaultValue=""
                          onChange={(e) => {
                            const id = Number(e.target.value);
                            if (id) toggleDual(a, true, id);
                          }}
                        >
                          <option value="">Добавить…</option>
                          {masters
                            .filter((m) => m.id !== a.primary_user_id)
                            .map((m) => (
                              <option key={m.id} value={m.id}>
                                {m.fio}
                              </option>
                            ))}
                        </select>
                      )}
                    </td>
                    <td>{a.version}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {tab === "urgent" && (
        <section className="panel form-panel">
          <h2>Срочная оценка</h2>
          <p className="muted">Выберите одного сотрудника и одного или нескольких оценщиков (мастер/прораб).</p>
          <div className="form-grid-2">
            <div>
              <label>
                Поиск сотрудника
                <input
                  placeholder="Начните вводить ФИО или табельный"
                  value={urgEmpQ}
                  onChange={(e) => setUrgEmpQ(e.target.value)}
                />
              </label>
              <label>
                Сотрудник
                <select value={urgEmpId} onChange={(e) => setUrgEmpId(e.target.value)} size={6} className="compact-list">
                  <option value="">— выберите —</option>
                  {employees
                    .filter((e) => {
                      const q = urgEmpQ.trim().toLowerCase();
                      if (!q) return true;
                      return e.fio.toLowerCase().includes(q) || e.tab_no.toLowerCase().includes(q);
                    })
                    .slice(0, 80)
                    .map((e) => (
                      <option key={e.id} value={e.id}>
                        {e.fio} ({e.tab_no})
                      </option>
                    ))}
                </select>
              </label>
            </div>
            <div>
              <label>
                Оценщики (Ctrl — несколько)
                <select
                  multiple
                  className="compact-list"
                  size={8}
                  value={urgEvalIds.map(String)}
                  onChange={(e) =>
                    setUrgEvalIds(Array.from(e.target.selectedOptions).map((o) => Number(o.value)))
                  }
                >
                  {masters.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.fio} · {m.role === "master" ? "мастер" : "прораб"}
                    </option>
                  ))}
                </select>
              </label>
              <p className="muted">Выбрано оценщиков: {urgEvalIds.length}</p>
              <button
                type="button"
                className="primary"
                disabled={busy || !urgEmpId || urgEvalIds.length === 0}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await apiCreateUrgent({
                      employee_id: Number(urgEmpId),
                      evaluator_user_ids: urgEvalIds,
                    });
                    setUrgEmpId("");
                    setUrgEvalIds([]);
                    setUrgEmpQ("");
                    setUrgent(await apiListUrgent());
                    setInfo("Срочная оценка создана");
                  } catch (e) {
                    setError(e instanceof Error ? e.message : "Ошибка");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Создать срочную
              </button>
            </div>
          </div>
          <h3 style={{ marginTop: "1rem" }}>Открытые и закрытые запросы</h3>
          <div className="excel-wrap mid">
            <table className="excel-table">
              <thead>
                <tr>
                  <th>№</th>
                  <th>Сотрудник</th>
                  <th>Таб. №</th>
                  <th>Статус</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {urgent.length === 0 && (
                  <tr>
                    <td colSpan={5} className="muted">
                      Пока нет срочных оценок
                    </td>
                  </tr>
                )}
                {urgent.map((u) => (
                  <tr key={u.id}>
                    <td>{u.id}</td>
                    <td>{u.fio}</td>
                    <td>{u.tab_no}</td>
                    <td>{u.status === "open" ? "открыта" : "закрыта"}</td>
                    <td>
                      {u.status === "open" && (
                        <button
                          type="button"
                          onClick={async () => {
                            await apiCloseUrgent(u.id);
                            setUrgent(await apiListUrgent());
                          }}
                        >
                          Закрыть
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {tab === "delegate" && (
        <section className="panel">
          <h2>Замещение</h2>
          <div className="row">
            <select value={delOrig} onChange={(e) => setDelOrig(e.target.value)}>
              <option value="">Кого замещаем…</option>
              {masters.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.fio}
                </option>
              ))}
            </select>
            <select value={delSub} onChange={(e) => setDelSub(e.target.value)}>
              <option value="">Кто замещает…</option>
              {masters.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.fio}
                </option>
              ))}
            </select>
            <input type="date" value={delFrom} onChange={(e) => setDelFrom(e.target.value)} />
            <input type="date" value={delTo} onChange={(e) => setDelTo(e.target.value)} />
            <button
              type="button"
              className="primary"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await apiCreateDelegation({
                    original_user_id: Number(delOrig),
                    substitute_user_id: Number(delSub),
                    starts_on: delFrom,
                    ends_on: delTo,
                  });
                  setDelegations(await apiDelegations());
                  setInfo("Замещение создано");
                } catch (e) {
                  setError(e instanceof Error ? e.message : "Ошибка");
                } finally {
                  setBusy(false);
                }
              }}
            >
              Создать
            </button>
          </div>
          <div className="excel-wrap">
            <table className="excel-table">
              <thead>
                <tr>
                  <th>Кого</th>
                  <th>Кто замещает</th>
                  <th>С</th>
                  <th>По</th>
                  <th>Статус</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {delegations.map((d) => (
                  <tr key={d.id}>
                    <td>{masterName(d.original_user_id)}</td>
                    <td>{masterName(d.substitute_user_id)}</td>
                    <td>{d.starts_on}</td>
                    <td>{d.ends_on}</td>
                    <td>{d.is_active ? "действует" : "снято"}</td>
                    <td>
                      {d.is_active && (
                        <button
                          type="button"
                          onClick={async () => {
                            await apiDeactivateDelegation(d.id);
                            setDelegations(await apiDelegations());
                          }}
                        >
                          Снять
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {tab === "employees" && (
        <section className="panel excel-panel">
          <h2>База сотрудников</h2>
          <div className="excel-toolbar">
            <input
              placeholder="Фильтр ФИО / таб.№"
              value={empQ}
              onChange={(e) => setEmpQ(e.target.value)}
            />
            <button
              type="button"
              onClick={async () =>
                setEmployees(await apiEmployees({ q: empQ || undefined, candidates: candOnly }))
              }
            >
              Применить
            </button>
            <label className="check">
              <input type="checkbox" checked={candOnly} onChange={(e) => setCandOnly(e.target.checked)} />
              только кандидаты
            </label>
          </div>
          <div className="row">
            <input placeholder="Табельный №" value={newTab} onChange={(e) => setNewTab(e.target.value)} />
            <input placeholder="ФИО" value={newFio} onChange={(e) => setNewFio(e.target.value)} />
            <button
              type="button"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await apiCreateEmployee({ tab_no: newTab, fio: newFio, is_candidate: false });
                  setNewTab("");
                  setNewFio("");
                  setEmployees(await apiEmployees({ q: empQ || undefined, candidates: candOnly }));
                  setInfo("Сотрудник добавлен");
                } catch (e) {
                  setError(e instanceof Error ? e.message : "Ошибка");
                } finally {
                  setBusy(false);
                }
              }}
            >
              Добавить в базу
            </button>
          </div>
          <div className="row">
            <select value={formalizeId} onChange={(e) => setFormalizeId(e.target.value)}>
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
              onChange={(e) => setFormalizeTab(e.target.value)}
            />
            <button
              type="button"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await apiFormalizeCandidate({
                    employee_id: Number(formalizeId),
                    new_tab_no: formalizeTab,
                  });
                  setFormalizeId("");
                  setFormalizeTab("");
                  setEmployees(await apiEmployees({ candidates: true }));
                  setInfo("Кандидат оформлен");
                } catch (e) {
                  setError(e instanceof Error ? e.message : "Ошибка");
                } finally {
                  setBusy(false);
                }
              }}
            >
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
                </tr>
              </thead>
              <tbody>
                {employees.map((e) => (
                  <tr key={e.id} className={e.is_candidate ? "row-info" : undefined}>
                    <td>{e.id}</td>
                    <td>{e.tab_no}</td>
                    <td>{e.fio}</td>
                    <td>{e.position_1c || "—"}</td>
                    <td>{e.is_candidate ? "да" : "нет"}</td>
                    <td>{e.hire_date || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {tab === "tickets" && (
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
                    onChange={(e) => setReplyDrafts((d) => ({ ...d, [t.id]: e.target.value }))}
                  />
                </label>
                <div className="row">
                  <button
                    type="button"
                    className="primary"
                    disabled={busy}
                    onClick={async () => {
                      setBusy(true);
                      try {
                        const note = (replyDrafts[t.id] ?? "").trim();
                        await apiPatchTicket(t.id, {
                          admin_note: note || undefined,
                          status: note ? "in_progress" : undefined,
                        });
                        setTickets(await apiTickets());
                        setInfo(`Ответ по обращению №${t.id} сохранён`);
                      } catch (e) {
                        setError(e instanceof Error ? e.message : "Ошибка");
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    Отправить ответ
                  </button>
                  {t.status !== "done" && (
                    <button
                      type="button"
                      onClick={async () => {
                        await apiPatchTicket(t.id, {
                          status: "done",
                          admin_note: (replyDrafts[t.id] ?? t.admin_note ?? "закрыто").trim(),
                        });
                        setTickets(await apiTickets());
                      }}
                    >
                      Закрыть обращение
                    </button>
                  )}
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      {tab === "events" && (
        <section className="panel">
          <h2>Журнал действий</h2>
          <div className="excel-wrap tall">
            <table className="excel-table">
              <thead>
                <tr>
                  <th>Когда</th>
                  <th>Объект</th>
                  <th>id</th>
                  <th>Действие</th>
                </tr>
              </thead>
              <tbody>
                {events.map((e) => (
                  <tr key={e.id}>
                    <td>{e.created_at}</td>
                    <td>{e.entity_type}</td>
                    <td>{e.entity_id}</td>
                    <td>{e.action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {tab === "import" && (
        <section className="panel">
          <h2>Загрузка Excel-файлов</h2>
          <p className="muted">
            Отдел мобилизации загружает три файла: база 1С, пользователи и реестр закрепления
            (03_Реестр_закрепления.xlsx). Можно выбрать файлы с компьютера или импортировать из папки Files на
            сервере.
          </p>

          <div className="upload-grid">
            <label className="upload-card">
              <strong>1. База 1С</strong>
              <span className="muted">файл 01_База_1С.xlsx</span>
              <input
                type="file"
                accept=".xlsx,.xls"
                onChange={(e) => setFileBase(e.target.files?.[0] || null)}
              />
              {fileBase && <span className="ok-text">{fileBase.name}</span>}
            </label>
            <label className="upload-card">
              <strong>2. Пользователи</strong>
              <span className="muted">файл 02_Пользователи.xlsx</span>
              <input
                type="file"
                accept=".xlsx,.xls"
                onChange={(e) => setFileUsers(e.target.files?.[0] || null)}
              />
              {fileUsers && <span className="ok-text">{fileUsers.name}</span>}
            </label>
            <label className="upload-card">
              <strong>3. Реестр закрепления</strong>
              <span className="muted">файл 03_Реестр_закрепления.xlsx</span>
              <input
                type="file"
                accept=".xlsx,.xls"
                onChange={(e) => setFileCarnet(e.target.files?.[0] || null)}
              />
              {fileCarnet && <span className="ok-text">{fileCarnet.name}</span>}
            </label>
          </div>

          <div className="row" style={{ marginTop: "1rem" }}>
            <button
              type="button"
              className="primary"
              disabled={busy || (!fileBase && !fileUsers && !fileCarnet)}
              onClick={runImportUpload}
            >
              {busy ? "Загрузка…" : "Загрузить выбранные файлы"}
            </button>
            <button type="button" disabled={busy} onClick={runImportFolder}>
              Импорт из папки Files на сервере
            </button>
          </div>
          <p className="muted" style={{ marginTop: "0.75rem" }}>
            После загрузки данные сразу попадают в назначения, базу и пользователей. Можно повторять импорт —
            строки обновятся.
          </p>
        </section>
      )}
    </div>
  );
}
