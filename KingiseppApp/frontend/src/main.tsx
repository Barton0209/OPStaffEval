import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Capacitor } from "@capacitor/core";
import "./styles.css";
import {
  apiHealth,
  apiLogin,
  apiMe,
  clearSession,
  getApiBase,
  getToken,
  setApiBase,
  type SessionUser,
} from "./api";
import { FieldApp } from "./FieldApp";
import { AdminApp } from "./AdminApp";
import { RegistryApp } from "./RegistryApp";
import { InstallBanner } from "./InstallBanner";

const isNative = Capacitor.isNativePlatform();

function App() {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [tabNo, setTabNo] = useState("");
  const [password, setPassword] = useState("");
  const [serverUrl, setServerUrl] = useState(getApiBase());
  const [showServer, setShowServer] = useState(isNative && !getApiBase());
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);
  const [online, setOnline] = useState(navigator.onLine);
  const [view, setView] = useState<"home" | "registry">("home");

  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);

  useEffect(() => {
    // SW только в браузере; в APK ассеты локальные
    if (!isNative && "serviceWorker" in navigator) {
      navigator.serviceWorker.register("./sw.js").catch(() => undefined);
    }
  }, []);

  useEffect(() => {
    (async () => {
      if (!getToken()) return;
      if (isNative && !getApiBase()) return;
      try {
        const me = await apiMe();
        setUser(me);
      } catch {
        clearSession();
      }
    })();
  }, []);

  async function checkServer() {
    setBusy(true);
    setError("");
    setInfo("");
    try {
      setApiBase(serverUrl);
      const h = await apiHealth();
      setInfo(`Сервер найден: ${h.org}`);
      setShowServer(false);
    } catch (e) {
      setError(
        e instanceof Error
          ? `Нет связи с сервером. Проверьте ссылку (должна начинаться с https://). ${e.message}`
          : "Сервер недоступен",
      );
    } finally {
      setBusy(false);
    }
  }

  async function onLogin(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (serverUrl.trim()) setApiBase(serverUrl);
      if (isNative && !getApiBase()) {
        setError("Сначала укажите адрес сервера (ссылка из туннеля)");
        setShowServer(true);
        return;
      }
      const session = await apiLogin(tabNo.trim(), password);
      setUser(session);
      setView("home");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Неверный логин или пароль");
    } finally {
      setBusy(false);
    }
  }

  function logout() {
    clearSession();
    setUser(null);
    setView("home");
  }

  if (!user) {
    return (
      <div className="page login">
        {!isNative && <InstallBanner />}
        <header className="hero-card" style={{ marginBottom: "1rem" }}>
          <p className="muted" style={{ margin: 0 }}>
            ВелесстройМонтаж · ОП Кингисепп{isNative ? " · Android" : ""}
          </p>
          <h1>Отдел мобилизации и координации</h1>
          <p className="muted">
            {isNative
              ? "В приложении укажите адрес сервера (из tunnel.bat), затем войдите табельным номером."
              : "Войдите табельным номером. С телефона — тот же вход."}
          </p>
        </header>

        <div className="login-banner" aria-hidden>
          <img src="./logo-velesstroy.png" alt="" />
        </div>

        {(showServer || isNative) && (
          <section className="panel" style={{ marginBottom: "0.85rem" }}>
            <h2>Адрес сервера</h2>
            <p className="muted">
              Вставьте ссылку из окна туннеля, например https://xxxx.trycloudflare.com — без слэша в конце.
            </p>
            <label>
              URL сервера
              <input
                value={serverUrl}
                onChange={(e) => setServerUrl(e.target.value)}
                placeholder="https://….trycloudflare.com"
                inputMode="url"
                autoCapitalize="none"
                autoCorrect="off"
              />
            </label>
            <button type="button" className="primary" disabled={busy} onClick={checkServer} style={{ width: "100%" }}>
              {busy ? "Проверка…" : "Проверить и сохранить"}
            </button>
            {info && <p className="ok-text">{info}</p>}
          </section>
        )}

        <form onSubmit={onLogin} className="panel">
          {!isNative && (
            <button className="link" type="button" onClick={() => setShowServer((v) => !v)}>
              {showServer ? "Скрыть адрес сервера" : "Другой сервер (туннель)…"}
            </button>
          )}
          <label>
            Табельный номер
            <input
              value={tabNo}
              onChange={(e) => setTabNo(e.target.value)}
              autoComplete="username"
              placeholder="например ВМ-0140784"
              required
            />
          </label>
          <label>
            Пароль
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </label>
          {error && <p className="error">{error}</p>}
          <button disabled={busy} type="submit" className="primary" style={{ width: "100%", minHeight: 48 }}>
            {busy ? "Входим…" : "Войти"}
          </button>
        </form>

        <div className="login-roles">
          <div className="login-role">
            <b>Мастер / прораб</b>
            Свой табельный → список людей → оценка → «Отправить».
          </div>
          <div className="login-role">
            <b>Отдел мобилизации (ADMIN-OP)</b>
            Назначения, срочные, база, загрузка Excel, реестр.
          </div>
        </div>
      </div>
    );
  }

  const isAdmin = user.role === "admin" || user.role === "admin_op";
  const isChief = user.role === "site_chief";
  const isField = user.role === "master" || user.role === "foreman";

  if (isChief || (isAdmin && view === "registry")) {
    return (
      <RegistryApp
        user={user}
        onLogout={logout}
        onBack={isAdmin ? () => setView("home") : undefined}
      />
    );
  }

  if (isAdmin) {
    return <AdminApp user={user} onLogout={logout} onOpenRegistry={() => setView("registry")} />;
  }

  if (isField) {
    return <FieldApp user={user} online={online} onLogout={logout} />;
  }

  return (
    <div className="page">
      <p className="error">Для вашей роли интерфейс пока не открыт.</p>
      <button type="button" onClick={logout}>
        Выйти
      </button>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
