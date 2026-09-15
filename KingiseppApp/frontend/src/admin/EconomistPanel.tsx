import { useEffect, useRef, useState } from "react";
import {
    apiEconomistEmployees,
    apiEconomistMissingRates,
    apiEconomistRateHistory,
    apiEconomistUpdateRate,
    type EconomistEmployee,
    type MissingRateItem,
    type RateHistoryRow,
} from "../api";

/** Форматирование даты в ISO (для input[type=date]). */
function todayIso() {
    const d = new Date();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${d.getFullYear()}-${m}-${day}`;
}

function fmtDate(iso: string | null | undefined) {
    if (!iso) return "—";
    const d = new Date(iso.length <= 10 ? `${iso}T00:00:00` : iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString("ru-RU");
}

function fmtMoney(v: number | null | undefined) {
    return v == null ? "—" : v.toLocaleString("ru-RU", { maximumFractionDigits: 2 });
}

export function EconomistPanel() {
    const [q, setQ] = useState("");
    const [candidates, setCandidates] = useState<EconomistEmployee[]>([]);
    const [picked, setPicked] = useState<EconomistEmployee | null>(null);
    const [changedAt, setChangedAt] = useState(todayIso());
    const [newRate, setNewRate] = useState("");
    const [comment, setComment] = useState("");
    const [busy, setBusy] = useState(false);
    const [msg, setMsg] = useState("");
    const [error, setError] = useState("");
    const [missing, setMissing] = useState<{ count: number; items: MissingRateItem[] }>({
        count: 0,
        items: [],
    });
    const [history, setHistory] = useState<RateHistoryRow[]>([]);
    const [showMissing, setShowMissing] = useState(false);
    const searchTimer = useRef<number | undefined>(undefined);

    useEffect(() => {
        apiEconomistMissingRates()
            .then(setMissing)
            .catch(() => undefined);
    }, []);

    useEffect(() => {
        window.clearTimeout(searchTimer.current);
        if (!q.trim()) {
            setCandidates([]);
            return;
        }
        searchTimer.current = window.setTimeout(() => {
            apiEconomistEmployees({ q: q.trim(), limit: 30 })
                .then(setCandidates)
                .catch(() => setCandidates([]));
        }, 300);
        return () => window.clearTimeout(searchTimer.current);
    }, [q]);

    useEffect(() => {
        if (!picked) {
            setHistory([]);
            return;
        }
        apiEconomistRateHistory(picked.id)
            .then(setHistory)
            .catch(() => setHistory([]));
    }, [picked]);

    function pickEmp(e: EconomistEmployee) {
        setPicked(e);
        setQ(e.fio);
        setCandidates([]);
        setNewRate(e.hourly_rate != null && e.hourly_rate > 0 ? String(e.hourly_rate) : "");
        setError("");
    }

    async function save() {
        if (!picked) {
            setError("Выберите сотрудника (начните вводить табельный или ФИО)");
            return;
        }
        const rate = Number(newRate.replace(",", "."));
        if (!Number.isFinite(rate) || rate <= 0) {
            setError("Введите корректную новую ЧТС (больше 0)");
            return;
        }
        if (!changedAt) {
            setError("Укажите дату изменения");
            return;
        }
        setBusy(true);
        setError("");
        setMsg("");
        try {
            await apiEconomistUpdateRate({
                tab_no: picked.tab_no,
                changed_at: changedAt,
                new_rate: rate,
                comment: comment.trim() || null,
            });
            setMsg(`ЧТС ${picked.fio} обновлена: ${fmtMoney(rate)} ₽ с ${fmtDate(changedAt)}`);
            // Обновляем данные сотрудника и бейдж.
            const [empRes, missingRes] = await Promise.all([
                apiEconomistEmployees({ q: picked.tab_no, limit: 5 }),
                apiEconomistMissingRates(),
            ]);
            const updated = empRes.find((x) => x.tab_no === picked.tab_no);
            if (updated) setPicked({ ...picked, ...updated });
            setMissing(missingRes);
            setNewRate("");
            setComment("");
            setHistory((h) => [
                {
                    id: Date.now(),
                    employee_id: picked.id,
                    old_rate: picked.hourly_rate,
                    new_rate: rate,
                    changed_at: changedAt,
                    comment: comment.trim() || null,
                    created_at: new Date().toISOString(),
                },
                ...h,
            ]);
        } catch (e) {
            setError(e instanceof Error ? e.message : "Не удалось сохранить");
        } finally {
            setBusy(false);
        }
    }

    return (
        <section className="panel">
            <h2>Экономист · ведение ЧТС</h2>

            <div className="economist-badge-row">
                <button
                    type="button"
                    className={missing.count > 0 ? "metric clickable warn" : "metric clickable"}
                    onClick={() => setShowMissing((v) => !v)}
                >
                    <div className="metric-ico" aria-hidden>⚙</div>
                    <div className="label">Без ЧТС</div>
                    <div className="value">{missing.count}</div>
                    <div className="hint">сотрудники со ставкой 0 / не заполнена</div>
                </button>
            </div>

            {showMissing && (
                <div className="economist-missing">
                    {missing.items.length === 0 ? (
                        <p className="ok-text">Все ЧТС заполнены 🎉</p>
                    ) : (
                        <ul className="plain-list">
                            {missing.items.map((it) => (
                                <li key={it.id}>
                                    <b>{it.fio}</b>{" "}
                                    <span className="muted">
                                        {it.tab_no} · {it.position_1c || "без должности"}
                                        {it.category ? ` · разряд ${it.category}` : ""}
                                    </span>
                                    <button
                                        type="button"
                                        className="link"
                                        onClick={() => pickEmp(it as unknown as EconomistEmployee)}
                                    >
                                        заполнить
                                    </button>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            )}

            <form
                onSubmit={(e) => {
                    e.preventDefault();
                    void save();
                }}
                className="economist-form"
            >
                <label>
                    Табельный номер или ФИО
                    <input
                        value={q}
                        onChange={(e) => {
                            setQ(e.target.value);
                            if (picked && e.target.value !== picked.fio) setPicked(null);
                        }}
                        placeholder="например ВМ-0140784"
                        autoComplete="off"
                    />
                </label>
                {candidates.length > 0 && !picked && (
                    <ul className="autocomplete">
                        {candidates.map((c) => (
                            <li key={c.id}>
                                <button type="button" onClick={() => pickEmp(c)}>
                                    <b>{c.fio}</b>{" "}
                                    <span className="muted">
                                        {c.tab_no} · {c.position_1c || "—"} · ЧТС {fmtMoney(c.hourly_rate)}
                                    </span>
                                </button>
                            </li>
                        ))}
                    </ul>
                )}

                {picked && (
                    <div className="economist-picked">
                        <table className="kv-table">
                            <tbody>
                                <tr>
                                    <th>Сотрудник</th>
                                    <td>
                                        {picked.fio} ({picked.tab_no})
                                    </td>
                                </tr>
                                <tr>
                                    <th>Должность</th>
                                    <td>{picked.position_1c || "—"}</td>
                                </tr>
                                <tr>
                                    <th>Разряд</th>
                                    <td>{picked.category || "—"}</td>
                                </tr>
                                <tr>
                                    <th>Текущая ЧТС</th>
                                    <td className={picked.is_rate_expired ? "rate-expired" : ""}>
                                        {fmtMoney(picked.hourly_rate)} ₽
                                        {picked.is_rate_expired ? " · просрочена ≥180 дней" : ""}
                                    </td>
                                </tr>
                                <tr>
                                    <th>Дата последнего повышения</th>
                                    <td>{fmtDate(picked.rate_last_raised)}</td>
                                </tr>
                                <tr>
                                    <th>Вилка по сетке</th>
                                    <td>
                                        {picked.tariff_min != null
                                            ? `${fmtMoney(picked.tariff_min)} — ${fmtMoney(picked.tariff_max)} ₽`
                                            : "нет данных"}
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                )}

                <label>
                    Дата изменения
                    <input
                        type="date"
                        value={changedAt}
                        onChange={(e) => setChangedAt(e.target.value)}
                        required
                    />
                </label>
                <label>
                    Новая ЧТС, ₽/час
                    <input
                        type="number"
                        step="0.01"
                        min="0.01"
                        value={newRate}
                        onChange={(e) => setNewRate(e.target.value)}
                        placeholder="например 415.50"
                        required
                    />
                </label>
                <label>
                    Комментарий
                    <input
                        value={comment}
                        onChange={(e) => setComment(e.target.value)}
                        placeholder="основание повышения (необязательно)"
                        maxLength={500}
                    />
                </label>

                {error && <p className="error">{error}</p>}
                {msg && <p className="ok-text">{msg}</p>}

                <button type="submit" className="primary" disabled={busy} style={{ width: "100%" }}>
                    {busy ? "Сохранение…" : "Сохранить изменение ЧТС"}
                </button>
            </form>

            {picked && history.length > 0 && (
                <div className="economist-history">
                    <h3>История изменений ЧТС — {picked.fio}</h3>
                    <table className="table">
                        <thead>
                            <tr>
                                <th>Дата</th>
                                <th>Было</th>
                                <th>Стало</th>
                                <th>Комментарий</th>
                            </tr>
                        </thead>
                        <tbody>
                            {history.map((h) => (
                                <tr key={h.id}>
                                    <td>{fmtDate(h.changed_at)}</td>
                                    <td>{fmtMoney(h.old_rate)}</td>
                                    <td>{fmtMoney(h.new_rate)}</td>
                                    <td>{h.comment || "—"}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </section>
    );
}