import { useEffect, useState } from "react";
import "./Login.css";

// ==================== API helpers ====================

async function apiGet(url: string, token?: string): Promise<any> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(url, { headers });
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
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

// ==================== Types ====================

interface Territory { code: string; name: string; }
interface RoleItem { code: string; name: string; }
interface CtrlUser { id: number; tab_no: string; fio: string; has_password: boolean; }

interface LoginResponse {
  requires_password_setup: boolean;
  access_token?: string;
  user: {
    id: number; tab_no: string; fio: string;
    role: string; organization_id: number;
    must_change_password?: boolean;
  };
}

// ==================== Slider ====================

const SLIDES = [
  { img: "./Files/UpLoad/Foto/Фото2.jpg", label: "" },
  { img: "./Files/UpLoad/Foto/Фото3.png", label: "" },
  { img: "./Files/UpLoad/Foto/Фото4.png", label: "" },
];

function Slider() {
  const [idx, setIdx] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (paused) return;
    const t = setInterval(() => setIdx((i) => (i + 1) % SLIDES.length), 5000);
    return () => clearInterval(t);
  }, [paused]);

  return (
    <div className="login-slider" onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)}>
      {SLIDES.map((s, i) => (
        <div
          key={i}
          className={`slide ${i === idx ? "active" : ""}`}
          style={{ backgroundImage: `url(${s.img})` }}
          onClick={() => setIdx(i)}
        />
      ))}
      <div className="slide-indicators">
        {SLIDES.map((_, i) => (
          <button key={i} className={`dot ${i === idx ? "active" : ""}`} onClick={() => setIdx(i)} />
        ))}
      </div>
    </div>
  );
}

// ==================== Main Login ====================

export function LoginScreen({ onLogin }: { onLogin: (token: string, user: any) => void }) {
  const [territories, setTerritories] = useState<Territory[]>([]);
  const [roles, setRoles] = useState<RoleItem[]>([]);
  const [users, setUsers] = useState<CtrlUser[]>([]);

  const [selTerritory, setSelTerritory] = useState("");
  const [selRole, setSelRole] = useState("");
  const [selUser, setSelUser] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Load territories
  useEffect(() => {
    apiGet("/api/auth/control/territories")
      .then(setTerritories)
      .catch(() => setTerritories([]));
  }, []);

  // Load roles when territory changes
  useEffect(() => {
    if (!selTerritory) { setRoles([]); setSelRole(""); setSelUser(""); setUsers([]); return; }
    apiGet(`/api/auth/control/roles?territory=${encodeURIComponent(selTerritory)}`)
      .then(setRoles)
      .catch(() => setRoles([]));
  }, [selTerritory]);

  // Load users when role changes
  useEffect(() => {
    if (!selTerritory || !selRole) { setSelUser(""); setUsers([]); return; }
    apiGet(`/api/auth/control/users?territory=${encodeURIComponent(selTerritory)}&role=${encodeURIComponent(selRole)}`)
      .then(setUsers)
      .catch(() => setUsers([]));
  }, [selTerritory, selRole]);

  const canLogin = selTerritory && selRole && selUser;

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    if (!canLogin) return;
    setBusy(true);
    setError("");
    try {
      const user = users.find((u) => u.id.toString() === selUser);
      const body: Record<string, unknown> = { tab_no: user?.tab_no || selUser };
      body.password = password;
      const resp: LoginResponse = await apiPost("/api/auth/control/login", body);
      if (resp.requires_password_setup) {
        // Переход на страницу создания пароля
        onLogin("", resp.user);
      } else if (resp.access_token) {
        onLogin(resp.access_token, resp.user);
      } else {
        onLogin("", resp.user);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка входа");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      {/* Левая часть — авторизация */}
      <div className="login-left">
        <div className="login-bg" style={{ backgroundImage: "url('./Files/UpLoad/Foto/фото5.png')" }} />
        <div className="login-overlay">
          <h1 className="login-title">Оценка рабочего персонала ОП и контроль показателей</h1>
          <form onSubmit={handleLogin} className="login-form">
            {/* 1. Выбор площадки */}
            <label className="login-field">
              <span>Выбор площадки для входа</span>
              <select
                value={selTerritory}
                onChange={(e) => { setSelTerritory(e.target.value); setSelRole(""); setSelUser(""); setUsers([]); setError(""); }}
                disabled={territories.length === 0}
                required
              >
                <option value="------">------</option>
                {territories.map((t) => (
                  <option key={t.code} value={t.name}>{t.name}</option>
                ))}
              </select>
            </label>

            {/* 2. Выбор отдела */}
            <label className="login-field">
              <span>Выбор отдела</span>
              <select
                value={selRole}
                onChange={(e) => { setSelRole(e.target.value); setSelUser(""); setUsers([]); setError(""); }}
                disabled={!selTerritory || roles.length === 0}
                required
              >
                <option value="------">------</option>
                {roles.map((r) => (
                  <option key={r.code} value={r.name}>{r.name}</option>
                ))}
              </select>
            </label>

            {/* 3. Выбор пользователя */}
            <label className="login-field">
              <span>Выбор пользователя</span>
              <select
                value={selUser}
                onChange={(e) => { setSelUser(e.target.value); setError(""); }}
                disabled={!selTerritory || !selRole || users.length === 0}
                required
              >
                <option value="------">------</option>
                {users.map((u) => (
                  <option key={u.id} value={u.id.toString()}>{u.fio} ({u.tab_no})</option>
                ))}
              </select>
            </label>

            <label className="login-field">
              <span>Пароль</span>
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => { setPassword(e.target.value); setError(""); }}
                disabled={!selUser}
                placeholder="При первом входе оставьте пустым"
              />
            </label>

            {error && <p className="login-error">{error}</p>}

            <div className="login-buttons">
              <button type="submit" disabled={!canLogin || busy} className="btn-primary">
                {busy ? "Входим…" : "Войти"}
              </button>
              <button type="button" className="btn-link" onClick={() => setError("Обратитесь к Администрации ОП для сброса пароля")}>
                Забыли пароль?
              </button>
            </div>
          </form>
          <footer className="login-footer">ООО «ВелесстройМонтаж», 2026 год</footer>
        </div>
      </div>

      {/* Правая часть — слайдер */}
      <div className="login-right">
        <Slider />
      </div>
    </div>
  );
}
