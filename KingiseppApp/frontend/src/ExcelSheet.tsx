import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type MouseEvent as ReactMouseEvent,
  type ReactNode,
} from "react";

export type ExcelColumn<T> = {
  id: string;
  title: string;
  width?: number;
  minWidth?: number;
  sticky?: "left" | "left2";
  filter?: "text" | "select" | "none";
  getValue: (row: T) => string;
  render?: (row: T) => ReactNode;
  cellClassName?: (row: T) => string | undefined;
  align?: "left" | "center" | "right";
};

type Props<T> = {
  rows: T[];
  columns: ExcelColumn<T>[];
  rowKey: (row: T) => string | number;
  rowClassName?: (row: T) => string | undefined;
  emptyText?: string;
  className?: string;
  /** Высота строки по умолчанию (px) */
  defaultRowHeight?: number;
  /** Видимые после фильтров/сортировки строки (для «отметить всех на экране») */
  onVisibleRowsChange?: (rows: T[]) => void;
};

type SortState = { id: string; dir: "asc" | "desc" } | null;

export function ExcelSheet<T>({
  rows,
  columns,
  rowKey,
  rowClassName,
  emptyText = "Нет данных",
  className = "",
  defaultRowHeight = 28,
  onVisibleRowsChange,
}: Props<T>) {
  const [widths, setWidths] = useState<Record<string, number>>(() =>
    Object.fromEntries(columns.map((c) => [c.id, c.width ?? 140])),
  );
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [openFilter, setOpenFilter] = useState<string | null>(null);
  const [sort, setSort] = useState<SortState>(null);
  const [rowHeight, setRowHeight] = useState(defaultRowHeight);
  const dragCol = useRef<{ id: string; startX: number; startW: number } | null>(null);
  const dragRow = useRef<{ startY: number; startH: number } | null>(null);
  const filterRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    function onMove(e: MouseEvent) {
      if (dragCol.current) {
        const col = columns.find((c) => c.id === dragCol.current!.id);
        const min = col?.minWidth ?? 60;
        const next = Math.max(min, dragCol.current.startW + (e.clientX - dragCol.current.startX));
        setWidths((w) => ({ ...w, [dragCol.current!.id]: next }));
      }
      if (dragRow.current) {
        const next = Math.max(22, Math.min(120, dragRow.current.startH + (e.clientY - dragRow.current.startY)));
        setRowHeight(next);
      }
    }
    function onUp() {
      dragCol.current = null;
      dragRow.current = null;
      document.body.classList.remove("xls-resizing");
    }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [columns]);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!filterRef.current) return;
      if (!filterRef.current.contains(e.target as Node)) setOpenFilter(null);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const uniqueByCol = useMemo(() => {
    const map: Record<string, string[]> = {};
    for (const col of columns) {
      if (col.filter === "none") continue;
      const set = new Set<string>();
      for (const row of rows) {
        const v = col.getValue(row).trim();
        if (v) set.add(v);
      }
      map[col.id] = [...set].sort((a, b) => a.localeCompare(b, "ru"));
    }
    return map;
  }, [columns, rows]);

  const view = useMemo(() => {
    let list = rows.filter((row) =>
      columns.every((col) => {
        const f = (filters[col.id] || "").trim().toLowerCase();
        if (!f || col.filter === "none") return true;
        return col.getValue(row).toLowerCase().includes(f);
      }),
    );
    if (sort) {
      const col = columns.find((c) => c.id === sort.id);
      if (col) {
        list = [...list].sort((a, b) => {
          const av = col.getValue(a);
          const bv = col.getValue(b);
          const cmp = av.localeCompare(bv, "ru", { numeric: true, sensitivity: "base" });
          return sort.dir === "asc" ? cmp : -cmp;
        });
      }
    }
    return list;
  }, [rows, columns, filters, sort]);

  useEffect(() => {
    onVisibleRowsChange?.(view);
  }, [view, onVisibleRowsChange]);

  const stickyLeft = useCallback(
    (sticky?: "left" | "left2") => {
      if (sticky === "left") return 0;
      if (sticky === "left2") {
        const first = columns.find((c) => c.sticky === "left");
        return first ? widths[first.id] ?? first.width ?? 44 : 44;
      }
      return undefined;
    },
    [columns, widths],
  );

  function startColResize(e: ReactMouseEvent, id: string) {
    e.preventDefault();
    e.stopPropagation();
    dragCol.current = { id, startX: e.clientX, startW: widths[id] ?? 140 };
    document.body.classList.add("xls-resizing");
  }

  function startRowResize(e: ReactMouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    dragRow.current = { startY: e.clientY, startH: rowHeight };
    document.body.classList.add("xls-resizing");
  }

  function toggleSort(id: string) {
    setSort((prev) => {
      if (!prev || prev.id !== id) return { id, dir: "asc" };
      if (prev.dir === "asc") return { id, dir: "desc" };
      return null;
    });
  }

  const totalWidth = columns.reduce((s, c) => s + (widths[c.id] ?? c.width ?? 140), 0);

  return (
    <div className={`xls-wrap ${className}`.trim()}>
      <div className="xls-toolbar-mini muted">
        Строк: {view.length}
        {view.length !== rows.length ? ` из ${rows.length}` : ""}
        {" · "}
        тяните край заголовка — ширина колонки; низ первой ячейки — высота строк
      </div>
      <div className="xls-scroll">
        <table className="xls-sheet" style={{ width: totalWidth, minWidth: "100%" }}>
          <colgroup>
            {columns.map((c) => (
              <col key={c.id} style={{ width: widths[c.id] ?? c.width ?? 140 }} />
            ))}
          </colgroup>
          <thead>
            <tr>
              {columns.map((col) => {
                const left = stickyLeft(col.sticky);
                const style: CSSProperties = {
                  width: widths[col.id],
                  minWidth: col.minWidth ?? 60,
                  ...(left != null ? { left } : {}),
                };
                const active = sort?.id === col.id;
                return (
                  <th
                    key={col.id}
                    className={[
                      "xls-th",
                      col.sticky ? `xls-sticky-${col.sticky}` : "",
                      filters[col.id] ? "xls-filtered" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                    style={style}
                  >
                    <div className="xls-th-inner">
                      <button type="button" className="xls-th-title" onClick={() => toggleSort(col.id)}>
                        {col.title}
                        {active ? (sort!.dir === "asc" ? " ▲" : " ▼") : ""}
                      </button>
                      {col.filter !== "none" && (
                        <button
                          type="button"
                          className={`xls-filter-btn ${filters[col.id] ? "on" : ""}`}
                          title="Фильтр"
                          onClick={(e) => {
                            e.stopPropagation();
                            setOpenFilter((v) => (v === col.id ? null : col.id));
                          }}
                        >
                          ▾
                        </button>
                      )}
                    </div>
                    {col.filter !== "none" && (
                      <input
                        className="xls-filter-input"
                        placeholder="Фильтр…"
                        value={filters[col.id] || ""}
                        onChange={(e) => setFilters((f) => ({ ...f, [col.id]: e.target.value }))}
                      />
                    )}
                    {openFilter === col.id && (
                      <div className="xls-filter-menu" ref={filterRef}>
                        <button
                          type="button"
                          className="xls-filter-clear"
                          onClick={() => {
                            setFilters((f) => ({ ...f, [col.id]: "" }));
                            setOpenFilter(null);
                          }}
                        >
                          Сбросить фильтр
                        </button>
                        <div className="xls-filter-values">
                          {(uniqueByCol[col.id] || []).slice(0, 80).map((val) => (
                            <button
                              key={val}
                              type="button"
                              className={filters[col.id] === val ? "active" : ""}
                              onClick={() => {
                                setFilters((f) => ({ ...f, [col.id]: val }));
                                setOpenFilter(null);
                              }}
                            >
                              {val}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                    <span
                      className="xls-col-resizer"
                      onMouseDown={(e) => startColResize(e, col.id)}
                      title="Изменить ширину"
                    />
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {view.length === 0 && (
              <tr>
                <td className="xls-empty" colSpan={columns.length}>
                  {emptyText}
                </td>
              </tr>
            )}
            {view.map((row, idx) => {
              const rk = rowKey(row);
              const rc = rowClassName?.(row);
              return (
                <tr
                  key={rk}
                  className={["xls-row", idx % 2 ? "xls-alt" : "", rc].filter(Boolean).join(" ")}
                  style={{ height: rowHeight }}
                >
                  {columns.map((col, ci) => {
                    const left = stickyLeft(col.sticky);
                    const style: CSSProperties = {
                      width: widths[col.id],
                      height: rowHeight,
                      textAlign: col.align || "left",
                      ...(left != null ? { left } : {}),
                    };
                    return (
                      <td
                        key={col.id}
                        className={[
                          "xls-td",
                          col.sticky ? `xls-sticky-${col.sticky}` : "",
                          col.cellClassName?.(row) || "",
                        ]
                          .filter(Boolean)
                          .join(" ")}
                        style={style}
                      >
                        {col.render ? col.render(row) : col.getValue(row)}
                        {ci === 0 && (
                          <span
                            className="xls-row-resizer"
                            onMouseDown={startRowResize}
                            title="Изменить высоту строк"
                          />
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
