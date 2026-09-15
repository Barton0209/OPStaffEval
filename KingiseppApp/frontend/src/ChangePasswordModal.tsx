import { useState } from "react";
import { apiChangePassword, type SessionUser } from "./api";

type Props = {
    onSuccess: (user: SessionUser) => void;
    onLogout: () => void;
};

export function ChangePasswordModal({ onSuccess, onLogout }: Props) {
    const [oldPwd, setOldPwd] = useState("");
    const [newPwd, setNewPwd] = useState("");
    const [confirm, setConfirm] = useState("");
    const [error, setError] = useState("");
    const [busy, setBusy] = useState(false);

    async function submit(e: React.FormEvent) {
        e.preventDefault();
        setError("");
        if (newPwd.length < 8) {
            setError("Новый пароль должен быть не короче 8 символов");
            return;
        }
        if (newPwd !== confirm) {
            setError("Пароли не совпадают");
            return;
        }
        setBusy(true);
        try {
            const user = await apiChangePassword(oldPwd, newPwd);
            onSuccess(user);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Не удалось сменить пароль");
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
            <form
                className="panel"
                onSubmit={submit}
                style={{ maxWidth: 420, width: "100%" }}
            >
                <h2>Смена пароля</h2>
                <p className="muted">
                    Система требует сменить временный пароль при первом входе. После смены все старые сессии будут завершены.
                </p>
                <label>
                    Текущий пароль
                    <input
                        type="password"
                        value={oldPwd}
                        onChange={(e) => setOldPwd(e.target.value)}
                        autoComplete="current-password"
                        required
                    />
                </label>
                <label>
                    Новый пароль
                    <input
                        type="password"
                        value={newPwd}
                        onChange={(e) => setNewPwd(e.target.value)}
                        autoComplete="new-password"
                        minLength={8}
                        required
                    />
                </label>
                <label>
                    Повторите новый пароль
                    <input
                        type="password"
                        value={confirm}
                        onChange={(e) => setConfirm(e.target.value)}
                        autoComplete="new-password"
                        required
                    />
                </label>
                {error && <p className="error">{error}</p>}
                <button
                    className="primary"
                    disabled={busy}
                    type="submit"
                    style={{ width: "100%", minHeight: 48 }}
                >
                    {busy ? "Сохраняем…" : "Сменить пароль"}
                </button>
                <button
                    type="button"
                    className="ghost"
                    onClick={onLogout}
                    style={{ width: "100%", marginTop: "0.5rem" }}
                >
                    Выйти
                </button>
            </form>
        </div>
    );
}