import { useEffect, useState } from "react";
import type { SessionUser } from "./api";

interface DepartmentInfo {
  department: string;
  ranges: Record<string, number>;
}

interface RangeEmployee {
  employee_id: number;
  tab_no: string;
  fio: string;
  position: string;
  site_name: string;
  final_score: number;
  hourly_rate: number | null;
  category: string | null;
  citizenship: string | null;
}

interface RangeInfo {
  department: string;
  range: string;
  count: number;
  employees: RangeEmployee[];
}

async function apiGet(url: string): Promise<any> {
  const token = localStorage.getItem("kingisepp_token");
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token || ""}` },
  });
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

async function apiPost(url: string, body: any): Promise<any> {
  const token = localStorage.getItem("kingisepp_token");
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token || ""}`,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    let detail = res.statusText;
    try { detail = JSON.parse(text).detail ?? text; } catch {}
    throw new Error(detail || res.statusText);
  }
  return res.json();
}

export function ManagementApp({ user, onLogout }: { user: SessionUser; onLogout: () => void }) {
  const [departments, setDepartments] = useState<string[]>([]);
  const [selectedDept, setSelectedDept] = useState<string | null>(null);
  const [rangeData, setRangeData] = useState<DepartmentInfo | null>(null);
  const [expandedRange, setExpandedRange] = useState<string | null>(null);
  const [rangeEmployees, setRangeEmployees] = useState<RangeInfo | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Загружаем список участков
  useEffect(() => {
    (async () => {
      try {
        setDepartments(await apiGet("/api/summary/departments"));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Ошибка загрузки");
      }
    })();
  }, []);

  // Загружаем диапазоны для участка
  async function loadRanges(dept: string) {
    setBusy(true);
    setError("");
    setSelectedDept(dept);
    setExpandedRange(null);
    setRangeEmployees(null);
    try {
      setRangeData(await apiGet(`/api/summary/departments/${encodeURIComponent(dept)}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки");
    } finally {
      setBusy(false);
    }
  }

  // Раскрытие диапазона
  async function loadRangeEmployees(dept: string, range: string) {
    setBusy(true);
    try {
      setRangeEmployees(await apiGet(`/api/summary/departments/${encodeURIComponent(dept)}/range/${encodeURIComponent(range)}`));
      setExpandedRange(range);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  // Выгрузка Excel диапазона
  async function exportRangeExcel(dept: string, range: string) {
    const token = localStorage.getItem("kingisepp_token");
    window.open(
      `/api/summary/departments/${encodeURIComponent(dept)}/range/${encodeURIComponent(range)}/export.xlsx?_token=${token}`,
      "_blank"
    );
  }

  // Выгрузка полного Excel
  async function exportAllEmployees() {
    const token = localStorage.getItem("kingisepp_token");
    window.open(`/api/employees/export.xlsx?_token=${token}`, "_blank");
  }

  // Выгрузка PDF
  async function exportPdf() {
    if (!rangeEmployees) return;
    try {
      await apiPost("/api/employees/export-pdf", {
        employee_ids: rangeEmployees.employees.map((e) => e.employee_id),
      });
      // Перенаправление на скачивание
      const token = localStorage.getItem("kingisepp_token");
      window.open(`/api/employees/export-pdf?_token=${token}`, "_blank");
    } catch (e) {
      alert(e instanceof Error ? e.message : "Ошибка PDF");
    }
  }

  const rangeColors: Record<string, string> = {
    "1 – 2": "#fee2e2",
    "2 – 3": "#fef3c7",
    "3 – 4": "#d1fae5",
    "4 – 5": "#dbeafe",
  };

  return (
    <div className="page">
      <header className="app-header">
        <span>👤 {user.fio} — Руководство ОП</span>
        <button type="button" onClick={onLogout}>Выйти</button>
      </header>
      <main className="app-main">
        <h2>Свод по участкам</h2>

        {error && <p className="error">{error}</p>}

        {/* Кнопка полной выгрузки */}
        <div style={{ marginBottom: 16 }}>
          <button className="primary" onClick={exportAllEmployees}>
            📊 Выгрузить всех сотрудников (Excel)
          </button>
        </div>

        {/* Список участков */}
        {!selectedDept && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {departments.map((dept) => (
              <button
                key={dept}
                className="primary"
                onClick={() => loadRanges(dept)}
                disabled={busy}
                style={{ padding: "12px 20px", fontSize: 14 }}
              >
                {dept}
              </button>
            ))}
            {departments.length === 0 && <p className="muted">Нет данных об участках.</p>}
          </div>
        )}

        {/* Диапазоны для участка */}
        {selectedDept && rangeData && (
          <div>
            <button
              type="button"
              onClick={() => { setSelectedDept(null); setRangeData(null); setExpandedRange(null); setRangeEmployees(null); }}
              style={{ marginBottom: 16 }}
            >
              ← Назад к участкам
            </button>
            <h3>{selectedDept}</h3>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 12 }}>
              {Object.entries(rangeData.ranges).map(([range, count]) => (
                <div
                  key={range}
                  onClick={() => loadRangeEmployees(selectedDept, range)}
                  style={{
                    padding: 16,
                    borderRadius: 10,
                    background: rangeColors[range] || "#f5f5f5",
                    cursor: "pointer",
                    border: expandedRange === range ? "2px solid #2563eb" : "2px solid transparent",
                    textAlign: "center",
                    transition: "transform 0.15s",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.transform = "scale(1.03)")}
                  onMouseLeave={(e) => (e.currentTarget.style.transform = "scale(1)")}
                >
                  <div style={{ fontSize: 24, fontWeight: 700 }}>{count}</div>
                  <div style={{ fontSize: 13, color: "#555" }}>оценка {range}</div>
                </div>
              ))}
            </div>

            {/* Раскрытый список сотрудников */}
            {rangeEmployees && (
              <div style={{ marginTop: 20 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                  <h4>Сотрудники: оценка {rangeEmployees.range} ({rangeEmployees.count} чел.)</h4>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button className="primary" onClick={() => exportRangeExcel(rangeEmployees.department, rangeEmployees.range)}>
                      📥 Excel
                    </button>
                    <button className="primary" onClick={exportPdf}>
                      📄 PDF
                    </button>
                  </div>
                </div>

                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ background: "#f5f5f5" }}>
                      <th style={thStyle}>Табельный</th>
                      <th style={thStyle}>ФИО</th>
                      <th style={thStyle}>Должность</th>
                      <th style={thStyle}>Оценка</th>
                      <th style={thStyle}>Разряд</th>
                      <th style={thStyle}>ЧТС</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rangeEmployees.employees.map((emp) => (
                      <tr key={emp.employee_id} style={{ borderBottom: "1px solid #eee" }}>
                        <td style={tdStyle}>{emp.tab_no}</td>
                        <td style={tdStyle}>{emp.fio}</td>
                        <td style={tdStyle}>{emp.position || "—"}</td>
                        <td style={{ ...tdStyle, fontWeight: 700 }}>{emp.final_score}</td>
                        <td style={tdStyle}>{emp.category || "—"}</td>
                        <td style={tdStyle}>{emp.hourly_rate || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

const thStyle: React.CSSProperties = {
  padding: "8px 12px",
  textAlign: "left",
  fontSize: 13,
  fontWeight: 600,
};

const tdStyle: React.CSSProperties = {
  padding: "8px 12px",
  fontSize: 13,
};
