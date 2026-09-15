import { useEffect, useRef, useState } from "react";
import { apiNotifications, type NotificationItem } from "./api";

type Props = {
    variant?: "topbar" | "nav";
};

/** Колокольчик уведомлений: счётчик неоценённых анкет + раскрывающийся список. */
export function NotificationBell({ variant = "topbar" }: Props) {
    const [count, setCount] = useState(0);
    const [items, setItems] = useState<NotificationItem[]>([]);
    const [open, setOpen] = useState(false);
    const wrapRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
        let alive = true;
        async function load() {
            try {
                const r = await apiNotifications();
                if (!alive) return;
                setCount(r.count);
                setItems(r.items);
            } catch {
                /* офлайн/нет прав — бейдж просто не показываем */
            }
        }
        void load();
        const timer = window.setInterval(load, 60_000);
        return () => {
            alive = false;
            window.clearInterval(timer);
        };
    }, []);

    useEffect(() => {
        if (!open) return;
        function onClick(e: MouseEvent) {
            if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
                setOpen(false);
            }
        }
        document.addEventListener("mousedown", onClick);
        return () => document.removeEventListener("mousedown", onClick);
    }, [open]);

    if (variant === "nav") {
        return (
            <button
                type="button"
                className={count > 0 ? "notif-btn has-new" : "notif-btn"}
                onClick={() => setOpen((v) => !v)}
                title={count > 0 ? "Есть неоценённые анкеты" : "Уведомления"}
            >
                <span className="ico">🔔</span>
                {count > 0 ? ` Уведомления · ${count}` : "Уведомления"}
            </button>
        );
    }

    return (
        <div className="notif-wrap" ref={wrapRef}>
            <button
                type="button"
                className={`pill ${count > 0 ? "notif-has" : "ghost"}`}
                onClick={() => setOpen((v) => !v)}
                title={count > 0 ? "Есть неоценённые анкеты" : "Уведомлений нет"}
            >
                🔔{count > 0 ? ` ${count}` : ""}
            </button>
            {open && (
                <div className="notif-drop">
                    {items.length === 0 ? (
                        <div className="muted notif-empty">Нет неоценённых анкет 🎉</div>
                    ) : (
                        <ul className="notif-list">
                            {items.map((it) => (
                                <li key={`${it.assignment_id}-${it.my_role}`}>
                                    <b>{it.fio}</b>{" "}
                                    <span className="muted">
                                        {it.tab_no} · {it.site_name || "—"} ·{" "}
                                        {it.my_role === "secondary" ? "2-й оценщик" : "1-й оценщик"}
                                    </span>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            )}
        </div>
    );
}