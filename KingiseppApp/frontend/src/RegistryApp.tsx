import { useEffect, useMemo, useState } from "react";
import { BrandHeader } from "./BrandHeader";
import {
  apiDownload,
  apiQuestionnaire,
  apiRegistryRows,
  apiUpsertKvyr,
  type Questionnaire,
  type RegistryRow,
  type SessionUser,
} from "./api";

type Props = {
  user: SessionUser;
  onLogout: () => void;
  onBack?: () => void;
};

type FilterMode = "all" | "closed" | "pending" | "stale";

export function RegistryApp({ user, onLogout, onBack }: Props) {
  const [rows, setRows] = useState<RegistryRow[]>([]);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<FilterMode>("all");
  const [filterMaster, setFilterMaster] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [coeff, setCoeff] = useState("1.0");
  const [selectedEmp, setSelectedEmp] = useState<number | null>(null);
  const [quest, setQuest] = useState<Questionnaire | null>(null);
  const [questLoading, setQuestLoading] = useState(false);
  const [exporting, setExporting] = useState<"" | "xlsx" | "pdf">("");
  const isChief = user.role === "site_chief";
  const canEditKvyr = isChief || user.role === "admin" || user.role === "admin_op";

  async function openQuestionnaire(assignmentId: number) {
    setQuestLoading(true);
    setError("");
    try {
      setQuest(await apiQuestionnaire(assignmentId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось открыть анкету");
    } finally {
      setQuestLoading(false);
    }
  }

  async function runExport(kind: "xlsx" | "pdf") {
    setExporting(kind);
    setError("");
    try {
      if (kind === "xlsx") {
        await apiDownload("/api/registry/export.xlsx", "reestr_ocenok.xlsx");
      } else {
        await apiDownload("/api/registry/export-questionnaires.pdf", "ankety.pdf");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось выгрузить файл");
    } finally {
      setExporting("");
    }
  }

  async function runExportOnePdf() {
    if (!quest) return;
    setExporting("pdf");
    setError("");
    try {
      const name = quest.employee.fio
        ? `anketa_${quest.employee.tab_no || quest.assignment_id}.pdf`
        : "anketa.pdf";
      await apiDownload(`/api/registry/questionnaire/${quest.assignment_id}/pdf`, name);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось выгрузить анкету PDF");
    } finally {
      setExporting("");
    }
  }

  async function load() {
    try {
      setRows(await apiRegistryRows());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось загрузить реестр");
    }
  }

  useEffect(() => {
    load();
  }, []);

  const masters = useMemo(() => {
    const map = new Map<string, string>();
    for (const r of rows) {
      if (r.primary_fio) map.set(r.primary_fio, r.primary_fio);
    }
    return [...map.keys()].sort((a, b) => a.localeCompare(b, "ru"));
  }, [rows]);

  const summary = useMemo(() => {
    const closed = rows.filter((r) => r.status === "закрыто").length;
    const partial = rows.filter((r) => r.status === "частично").length;
    const waiting = rows.filter((r) => r.status === "ожидает").length;
    const stale = rows.filter((r) => r.tariff_stale).length;
    return { closed, partial, waiting, stale, total: rows.length };
  }, [rows]);

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    return rows.filter((r) => {
      if (filter === "closed" && r.status !== "закрыто") return false;
      if (filter === "pending" && !(r.status === "ожидает" || r.status === "частично")) return false;
      if (filter === "stale" && !r.tariff_stale) return false;
      if (filterMaster && (r.primary_fio || "") !== filterMaster) return false;
      if (!s) return true;
      return (
        r.fio.toLowerCase().includes(s) ||
        r.tab_no.toLowerCase().includes(s) ||
        (r.primary_fio || "").toLowerCase().includes(s)
      );
    });
  }, [rows, q, filter, filterMaster]);

  function clearSelection() {
    setSelectedEmp(null);
    setCoeff("1.0");
    setInfo("");
  }

  async function saveKvyr() {
    if (!selectedEmp) return;
    try {
      await apiUpsertKvyr({ employee_id: selectedEmp, coeff: Number(coeff) });
      setInfo(`Коэффициент выработки ${coeff} сохранён`);
      clearSelection();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось сохранить коэффициент");
    }
  }

  const selectedRow = selectedEmp ? rows.find((r) => r.employee_id === selectedEmp) : null;

  const filterLabel =
    filter === "all"
      ? "все строки"
      : filter === "closed"
        ? "закрыто"
        : filter === "pending"
          ? "ожидают / частично"
          : "старый тариф";

  return (
    <div className="page excel-page">
      <BrandHeader
        title={isChief ? "Начальник участка · реестр" : "Отдел мобилизации и координации ОП Кингисепп"}
        subtitle="Реестр оценок · итоговые баллы, Квыр и тариф"
        right={
          <>
            {onBack && (
              <button type="button" onClick={onBack}>
                ← К управлению
              </button>
            )}
            <button className="ghost" type="button" onClick={onLogout}>
              Выйти
            </button>
          </>
        }
      />

      <section className="dash-grid">
        <button
          type="button"
          className={`metric clickable ${filter === "all" ? "metric-active" : ""}`}
          onClick={() => setFilter("all")}
        >
          <div className="metric-ico" aria-hidden>
            📋
          </div>
          <div className="label">Всего в реестре</div>
          <div className="value">{summary.total}</div>
          <div className="hint">показать все строки</div>
        </button>
        <button
          type="button"
          className={`metric ok clickable ${filter === "closed" ? "metric-active" : ""}`}
          onClick={() => setFilter("closed")}
        >
          <div className="metric-ico" aria-hidden>
            ✅
          </div>
          <div className="label">Закрыто / готово</div>
          <div className="value">{summary.closed}</div>
          <div className="hint">фильтр: статус «закрыто»</div>
        </button>
        <button
          type="button"
          className={`metric warn clickable ${filter === "pending" ? "metric-active" : ""}`}
          onClick={() => setFilter("pending")}
        >
          <div className="metric-ico" aria-hidden>
            ⏳
          </div>
          <div className="label">Ожидают / частично</div>
          <div className="value">{summary.waiting + summary.partial}</div>
          <div className="hint">ещё без итога</div>
        </button>
        <button
          type="button"
          className={`metric clickable ${summary.stale ? "danger" : "ok"} ${filter === "stale" ? "metric-active" : ""}`}
          onClick={() => setFilter("stale")}
        >
          <div className="metric-ico" aria-hidden>
            ⚠
          </div>
          <div className="label">Старый тариф (≥6 мес.)</div>
          <div className="value">{summary.stale}</div>
          <div className="hint">фильтр по тарифу</div>
        </button>
      </section>

      <div className="excel-toolbar">
        <input
          className="search"
          style={{ marginBottom: 0, flex: 1 }}
          placeholder="Поиск по ФИО или табельному"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <label className="toolbar-select">
          Мастер / прораб
          <select value={filterMaster} onChange={(e) => setFilterMaster(e.target.value)}>
            <option value="">Все</option>
            {masters.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
        <span className="pill info">Фильтр: {filterLabel}</span>
        <span className="muted">Строк: {filtered.length}</span>
        <button type="button" className="ghost" disabled={exporting !== ""} onClick={() => runExport("xlsx")}>
          {exporting === "xlsx" ? "Выгружаю…" : "⬇ Выгрузить реестр"}
        </button>
        <button type="button" className="ghost" disabled={exporting !== ""} onClick={() => runExport("pdf")}>
          {exporting === "pdf" ? "Выгружаю…" : "⬇ Выгрузить анкеты (PDF)"}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {info && <p className="ok-text">{info}</p>}

      {canEditKvyr && selectedEmp && (
        <div className="row panel">
          <span>
            Выбран: <strong>{selectedRow?.fio || `id=${selectedEmp}`}</strong>
            {selectedRow?.tab_no ? ` · ${selectedRow.tab_no}` : ""}
          </span>
          <input
            value={coeff}
            onChange={(e) => setCoeff(e.target.value)}
            style={{ width: 90 }}
            aria-label="Коэффициент выработки"
          />
          <button type="button" className="primary" onClick={saveKvyr}>
            Сохранить Квыр
          </button>
          <button type="button" className="ghost" onClick={clearSelection}>
            Отмена
          </button>
        </div>
      )}

      <div className="excel-wrap tall">
        <table className="excel-table sticky">
          <thead>
            <tr>
              <th className="sticky-col">Таб. №</th>
              <th className="sticky-col-2">ФИО</th>
              <th>Оценщики</th>
              <th>Квыр</th>
              <th>Итог</th>
              <th>Статус</th>
              <th>Испыт.</th>
              <th>Тариф</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
              <tr
                key={`${r.assignment_id}-${r.tab_no}`}
                className={[
                  r.tariff_stale ? "row-warn" : "",
                  r.probation_active ? "row-probation" : "",
                  selectedEmp === r.employee_id ? "row-selected" : "",
                ]
                  .filter(Boolean)
                  .join(" ") || undefined}
                onClick={() => r.employee_id && setSelectedEmp(r.employee_id)}
              >
                <td className="sticky-col">{r.tab_no}</td>
                <td className="sticky-col-2">
                  <button
                    type="button"
                    className="link fio-link"
                    title="Открыть объединённую анкету (оба оценщика)"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (r.assignment_id) void openQuestionnaire(r.assignment_id);
                    }}
                  >
                    {r.fio}
                  </button>
                </td>
                <td>
                  {isChief ? (
                    <span className="muted">скрыто для начальника</span>
                  ) : (
                    <>
                      <div>
                        {r.primary_fio || "—"}
                        {r.primary_avg != null ? ` (${r.primary_avg})` : ""}
                      </div>
                      {r.secondary_fio ? (
                        <div className="muted">
                          {r.secondary_fio}
                          {r.secondary_avg != null ? ` (${r.secondary_avg})` : ""}
                        </div>
                      ) : null}
                    </>
                  )}
                </td>
                <td>{r.k_vyr ?? "—"}</td>
                <td>{r.final_score ?? "—"}</td>
                <td>{r.status}</td>
                <td>
                  {r.probation_active && r.probation_end_date ? (
                    <span className="pill warn" title="Идёт испытательный срок">
                      до {r.probation_end_date}
                    </span>
                  ) : r.probation_end_date ? (
                    <span className="muted">{r.probation_end_date}</span>
                  ) : (
                    "—"
                  )}
                </td>
                <td
                  className={r.is_rate_expired ? "rate-expired" : undefined}
                  title={r.is_rate_expired ? "ЧТС не повышалась более 6 месяцев!" : undefined}
                >
                  {r.hourly_rate ?? "—"}
                  {r.is_rate_expired && " ⚠"}
                  {r.rate_last_raised ? <div className="muted">{r.rate_last_raised}</div> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted">
        Карточка сверху — фильтр по статусу. Список «Мастер / прораб» — по основному оценщику. Жёлтая строка —
        тариф ≥6 мес. Клик по строке — ввод Квыр, «Отмена» снимает выбор. Клик по ФИО — объединённая анкета.
      </p>

      {questLoading && <p className="muted">Открываю анкету…</p>}

      {quest && (
        <div className="modal-overlay" onClick={() => setQuest(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <div>
                <h2 style={{ margin: 0 }}>Объединённая анкета · {quest.period_code}</h2>
                <p className="muted" style={{ margin: 0 }}>
                  <strong>{quest.employee.fio}</strong> · таб. {quest.employee.tab_no} ·{" "}
                  {quest.employee.position || "—"} · {quest.employee.site_name || "—"}
                </p>
                {quest.employee.hourly_rate != null && (
                  <p className="muted" style={{ margin: 0 }}>
                    ЧТС:{" "}
                    <span
                      className={quest.employee.is_rate_expired ? "rate-expired" : undefined}
                      title={
                        quest.employee.is_rate_expired
                          ? "ЧТС не повышалась более 6 месяцев!"
                          : undefined
                      }
                    >
                      {quest.employee.hourly_rate} ₽/ч
                    </span>
                    {quest.employee.is_rate_expired && (
                      <span className="rate-expired" title="ЧТС не повышалась более 6 месяцев!">
                        {" "}⚠
                      </span>
                    )}
                    {quest.employee.rate_last_raised
                      ? ` · поднятие ${quest.employee.rate_last_raised}`
                      : quest.employee.rate_updated_at
                        ? ` · изм. ${quest.employee.rate_updated_at}`
                        : ""}
                    {quest.employee.tariff_min != null &&
                      ` · вилка ${quest.employee.tariff_min}–${quest.employee.tariff_max ?? "—"}`}
                  </p>
                )}
                {quest.employee.probation_end_date && (
                  <p className="muted" style={{ margin: 0 }}>
                    Испытательный срок
                    {quest.employee.probation_active ? (
                      <>
                        {" "}
                        <span className="pill warn">до {quest.employee.probation_end_date}</span>
                      </>
                    ) : (
                      <> окончен · {quest.employee.probation_end_date}</>
                    )}
                  </p>
                )}
              </div>
              <div className="modal-head-actions">
                <button
                  type="button"
                  className="primary"
                  disabled={exporting !== ""}
                  onClick={() => void runExportOnePdf()}
                >
                  {exporting === "pdf" ? "Формирую…" : "🖨 Печать / Экспорт PDF"}
                </button>
                <button type="button" className="ghost" onClick={() => setQuest(null)}>
                  ✕ Закрыть
                </button>
              </div>
            </div>

            <div className="excel-wrap" style={{ maxHeight: "50vh" }}>
              <table className="excel-table">
                <thead>
                  <tr>
                    <th>Параметр</th>
                    <th>
                      1-й оценщик
                      {quest.primary?.fio ? (
                        <>
                          <br />
                          <span className="muted">{quest.primary.fio}</span>
                        </>
                      ) : null}
                    </th>
                    <th>
                      2-й оценщик
                      {quest.secondary?.fio ? (
                        <>
                          <br />
                          <span className="muted">{quest.secondary.fio}</span>
                        </>
                      ) : null}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {quest.criteria.map((c) => (
                    <tr key={c.key}>
                      <td>{c.title}</td>
                      <td style={{ textAlign: "center" }}>{quest.primary?.scores[c.key] ?? "—"}</td>
                      <td style={{ textAlign: "center" }}>{quest.secondary?.scores[c.key] ?? "—"}</td>
                    </tr>
                  ))}
                  <tr>
                    <td>
                      <strong>Средний балл</strong>
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <strong>{quest.primary?.avg ?? "—"}</strong>
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <strong>{quest.secondary?.avg ?? "—"}</strong>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div className="quest-summary">
              <span>
                Общая оценка: <strong>{quest.combined_avg ?? "—"}</strong>
              </span>
              <span>
                Квыр: <strong>{quest.k_vyr}</strong>
              </span>
              <span>
                Итог: <strong>{quest.final_score ?? "—"}</strong>
              </span>
              <span className={`pill ${quest.status === "закрыто" ? "ok" : "warn"}`}>{quest.status}</span>
            </div>

            <div className="quest-evaluators muted">
              <div>
                1-й: {quest.primary?.fio || "—"}
                {quest.primary?.role_ru ? ` (${quest.primary.role_ru})` : ""} ·{" "}
                {quest.primary?.submitted_at
                  ? `сдана ${new Date(quest.primary.submitted_at).toLocaleDateString("ru-RU")}`
                  : "не сдана"}
              </div>
              <div>
                2-й: {quest.secondary?.fio || "—"}
                {quest.secondary?.role_ru ? ` (${quest.secondary.role_ru})` : ""} ·{" "}
                {quest.secondary?.submitted_at
                  ? `сдана ${new Date(quest.secondary.submitted_at).toLocaleDateString("ru-RU")}`
                  : "не сдана"}
              </div>
              {quest.primary?.comment && <div>Комментарий 1-го: {quest.primary.comment}</div>}
              {quest.secondary?.comment && <div>Комментарий 2-го: {quest.secondary.comment}</div>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
