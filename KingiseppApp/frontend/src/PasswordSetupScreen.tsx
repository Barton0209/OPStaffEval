import { useState } from "react";

interface Props {
  user: { id: number; tab_no: string; fio: string; role: string; organization_id: number };
  onSuccess: (token: string, user: any) => void;
  onLogout: () => void;
}

async function apiPost(url: string, body: Record<string, unknown>): Promise<any> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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

export function PasswordSetupScreen({ user, onSuccess, onLogout }: Props) {
  const [pwd, setPwd] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (pwd.length < 8) { setError("Пароль минимум 8 символов"); return; }
    if (pwd !== confirm) { setError("Пароли не совпадают"); return; }
    setBusy(true);
    setError("");
    try {
      const resp: any = await apiPost("/api/auth/control/setup-password", {
        user_id: user.id,
        new_password: pwd,
      });
      onSuccess(resp.access_token, resp.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка создания пароля");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", background: "#f0f4f8" }}>
      <div style={{ background: "#fff", borderRadius: 16, padding: "2.5rem 2rem", maxWidth: 420, width: "100%", boxShadow: "0 8px 32px rgba(0,0,0,0.12)" }}>
        <h2 style={{ textAlign: "center", margin: "0 0 0.5rem", color: "#1a1a2e" }}>Создание пароля</h2>
        <p style={{ textAlign: "center", color: "#666", fontSize: 0.9, margin: "0 0 1.5rem" }}>
          Здравствуйте, {user.fio}! Установите пароль для входа в систему.
        </p>
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 1 }}>
          <label style={{ display: "flex", flexDirection: "column", gap: 0.35 }}>
            <span style={{ fontSize: 0.82, fontWeight: 600, color: "#333" }}>Пароль</span>
            <input
              type="password"
              value={pwd}
              onChange={(e) => setPwd(e.target.value)}
              required
              style={{ height: 44, border: "1.5px solid #d0d0d0", borderRadius: 8, padding: "0 0.75rem", fontSize: 0.95 }}
            />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 0.35 }}>
            <span style={{ fontSize: 0.82, fontWeight: 600, color: "#333" }}>Подтвердите пароль</span>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
              style={{ height: 44, border: "1.5px solid #d0d0d0", borderRadius: 8, padding: "0 0.75rem", fontSize: 0.95 }}
            />
          </label>
          {error && <p style={{ color: "#dc2626", fontSize: 0.85, margin: 0, padding: 0.5, background: "#fef2f2", borderRadius: 6, textAlign: "center" }}>{error}</p>}
          <button type="submit" disabled={busy} style={{ height: 46, border: "none", borderRadius: 10, background: busy ? "#93b4f5" : "#2563eb", color: "#fff", fontSize: 1, fontWeight: 600, cursor: busy ? "not-allowed" : "pointer", marginTop: 0.5 }}>
            {busy ? "Создаём…" : "Создать пароль"}
          </button>
        </form>
        <div style={{ textAlign: "center", marginTop: 1.25 }}>
          <button type="button" onClick={onLogout} style={{ background: "none", border: "none", color: "#2563eb", fontSize: 0.85, cursor: "pointer" }}>
            Вернуться к входу
          </button>
        </div>
      </div>
    </div>
  );
}
