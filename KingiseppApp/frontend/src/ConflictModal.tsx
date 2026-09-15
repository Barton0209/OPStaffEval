import { useState } from "react";
import { apiDiscardDraft } from "./api";

type ConflictDiff = {
    current_version?: number;
    submitted_version?: number | null;
    server_changes?: Record<string, unknown> | null;
    changed_at?: string | null;
};

export type ConflictData = {
    assignment_id?: number | null;
    conflict_message?: string | null;
    conflict_diff?: ConflictDiff | null;
};

type Props = {
    data: ConflictData;
    onRefill: () => void;
    onDiscarded: () => void;
};

function formatValue(v: unknown): string {
    if (v === null || v === undefined) return "—";
    if (typeof v === "object") return JSON.stringify(v);
    return String(v);
}

export function ConflictModal({ data, onRefill, onDiscarded }: Props) {
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");
    const diff = data.conflict_diff;
    const changes = diff?.server_changes ?? {};

    async function discard() {
        setBusy(true);
        setError("");
        try {
            if (data.assignment_id != null) {
                await apiDiscardDraft(data.assignment_id);
            }
            onDiscarded();
        } catch (e) {
            setError(e instanceof Error ? e.message : "Не удалось отменить черновик");
        } finally {
            setBusy(false);
        }
    }

    return (
        <div
            style={{
                position: "fixed",
                inset: 0,
                background: "rgba(6, 24, 18, 0.82)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                zIndex: 1000,
                padding: "1rem",
            }}
        >
            <div className="panel" style={{ maxWidth: 480, width: "100%" }}>
                <h2>Конфликт версии</h2>
                <p className="muted">{data.conflict_message}</p>
                <p className="muted">
                    Версия на сервере: <strong>{diff?.current_version ?? "?"}</strong>
                    {diff?.submitted_version != null && <> · ваша версия: {diff.submitted_version}</>}
                    {diff?.changed_at ? (
                        <>
                            {" "}
                            · изменено: {new Date(diff.changed_at).toLocaleString("ru-RU")}
                        </>
                    ) : null}
                </p>
                {Object.keys(changes).length > 0 && (
                    <div>
                        <h3 style={{ fontSize: "1rem", marginBottom: "0.35rem" }}>
                            Что изменил администратор:
                        </h3>
                        <ul style={{ margin: 0, paddingLeft: "1.1rem" }}>
                            {Object.entries(changes).map(([k, v]) => (
                                <li key={k}>
                                    <code>{k}</code>: {formatValue(v)}
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
                {error && <p className="error">{error}</p>}
                <button
                    type="button"
                    className="primary"
                    disabled={busy}
                    onClick={onRefill}
                    style={{ width: "100%", minHeight: 44 }}
                >
                    Перезаполнить анкету
                </button>
                <button
                    type="button"
                    className="ghost"
                    disabled={busy}
                    onClick={() => void discard()}
                    style={{ width: "100%", marginTop: "0.5rem" }}
                >
                    {busy ? "Отменяем…" : "Отменить черновик"}
                </button>
            </div>
        </div>
    );
}