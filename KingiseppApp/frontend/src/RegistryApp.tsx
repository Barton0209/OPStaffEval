import { useEffect, useMemo, useState } from "react";
import { BrandHeader } from "./BrandHeader";
import { apiRegistryRows, apiUpsertKvyr, type RegistryRow, type SessionUser } from "./api";

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
  const isChief = user.role === "site_chief";
  const canEditKvyr = isChief || user.role === "admin" || user.role === "admin_op";

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
              <th>Основной</th>
              <th>Балл</th>
              <th>Второй</th>
              <th>Квыр</th>
              <th>Итог</th>
              <th>Статус</th>
              <th>Тариф</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
              <tr
                key={`${r.assignment_id}-${r.tab_no}`}
                className={[
                  r.tariff_stale ? "row-warn" : "",
                  selectedEmp === r.employee_id ? "row-selected" : "",
                ]
                  .filter(Boolean)
                  .join(" ") || undefined}
                onClick={() => r.employee_id && setSelectedEmp(r.employee_id)}
              >
                <td className="sticky-col">{r.tab_no}</td>
                <td className="sticky-col-2">{r.fio}</td>
                <td>{r.primary_fio || "—"}</td>
                <td>{r.primary_avg ?? "—"}</td>
                <td>
                  {r.secondary_fio || "—"}
                  {r.secondary_avg != null ? ` (${r.secondary_avg})` : ""}
                </td>
                <td>{r.k_vyr ?? "—"}</td>
                <td>{r.final_score ?? "—"}</td>
                <td>{r.status}</td>
                <td>
                  {r.hourly_rate ?? "—"}
                  {r.tariff_stale ? " ⚠" : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted">
        Карточка сверху — фильтр по статусу. Список «Мастер / прораб» — по основному оценщику. Жёлтая строка —
        тариф ≥6 мес. Клик по строке — ввод Квыр, «Отмена» снимает выбор.
      </p>
    </div>
  );
}
