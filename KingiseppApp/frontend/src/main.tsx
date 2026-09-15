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
  setRequirePasswordChangeHandler,
  type SessionUser,
} from "./api";
import { FieldApp } from "./FieldApp";
import { AdminApp } from "./AdminApp";
import { EconomistApp } from "./EconomistApp";
import { RegistryApp } from "./RegistryApp";
import { InstallBanner } from "./InstallBanner";
import { ChangePasswordModal } from "./ChangePasswordModal";
import { LoginScreen } from "./LoginScreen";
import { PasswordSetupScreen } from "./PasswordSetupScreen";
import { ManagementApp } from "./ManagementApp";

const isNative = Capacitor.isNativePlatform();

// Типы для ролей
type AppRole = SessionUser["role"] | "management_op" | "cok_okit" | "cok_adapt" | "cok_otiz";

interface CtrlUserPayload {
  id: number;
  tab_no: string;
  fio: string;
  role: string;
  organization_id: number;
  must_change_password?: boolean;
}

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
  const [showChangePwd, setShowChangePwd] = useState(false);

  // Состояние "Контроль" входа
  const [ctrlPendingUser, setCtrlPendingUser] = useState<CtrlUserPayload | null>(null);

  useEffect(() => {
    setRequirePasswordChangeHandler(() => setShowChangePwd(true));
    return () => setRequirePasswordChangeHandler(null);
  }, []);

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
        if (me.must_change_password) setShowChangePwd(true);
      } catch (e) {
        const err = e as { requirePasswordChange?: boolean };
        if (err?.requirePasswordChange) {
          const raw = localStorage.getItem("kingisepp_user");
          if (raw) {
            try {
              setUser(JSON.parse(raw));
              setShowChangePwd(true);
              return;
            } catch { /* ignore */ }
          }
        }
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
      if (session.must_change_password) setShowChangePwd(true);
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
    setShowChangePwd(false);
    setCtrlPendingUser(null);
  }

  // Обработчик успешного входа из "Контроль"
  function onCtrlLogin(token: string, ctrlUser: CtrlUserPayload) {
    if (token) {
      // Обычный вход — токен получен
      setUser({
        id: ctrlUser.id,
        tab_no: ctrlUser.tab_no,
        fio: ctrlUser.fio,
        role: ctrlUser.role as AppRole,
        organization_id: ctrlUser.organization_id,
        must_change_password: ctrlUser.must_change_password ?? false,
      });
    } else {
      // Первый вход — нужен setup пароля
      setCtrlPendingUser(ctrlUser);
    }
  }

  // После установки пароля — автоматический вход
  function onPasswordSetupDone(token: string, setupUser: any) {
    setUser({
      id: setupUser.id,
      tab_no: setupUser.tab_no,
      fio: setupUser.fio,
      role: setupUser.role as AppRole,
      organization_id: setupUser.organization_id,
      must_change_password: false,
    });
    setCtrlPendingUser(null);
  }

  if (showChangePwd && user) {
    return (
      <ChangePasswordModal
        onSuccess={(u) => {
          setUser(u);
          setShowChangePwd(false);
        }}
        onLogout={logout}
      />
    );
  }

  // Страница создания пароля (первый вход "Контроль")
  if (ctrlPendingUser) {
    return (
      <PasswordSetupScreen
        user={ctrlPendingUser}
        onSuccess={onPasswordSetupDone}
        onLogout={logout}
      />
    );
  }

  if (!user) {
    return (
      <>
        {!isNative && <InstallBanner />}
        <LoginScreen onLogin={onCtrlLogin} />
      </>
    );
  }

  const isAdmin = user.role === "admin" || user.role === "admin_op";
  const isChief = user.role === "site_chief";
  const isField = user.role === "master" || user.role === "foreman";
  const isEconomist = user.role === "economist";
  const isManagement = user.role === "management_op";
  const isCok = ["cok_okit", "cok_adapt", "cok_otiz"].includes(user.role);

  // Экономист
  if (isEconomist) {
    return <EconomistApp user={user} onLogout={logout} />;
  }

  // Руководитель ОП
  if (isManagement) {
    return <ManagementApp user={user} onLogout={logout} />;
  }

  // ЦОК
  if (isCok) {
    return (
      <div className="page">
        <header className="app-header">
          <span>👤 {user.fio}</span>
          <button type="button" onClick={logout}>Выйти</button>
        </header>
        <main className="app-main">
          <h2>ЦОК — {user.role}</h2>
          <p className="muted">Кабинет в разработке. Права определяются ролью ЦОК.</p>
        </main>
      </div>
    );
  }

  // Начальник участка
  if (isChief) {
    if (view === "registry") {
      return <RegistryApp user={user} onLogout={logout} onBack={() => setView("home")} />;
    }
    return (
      <FieldApp
        user={user}
        online={online}
        onLogout={logout}
        onOpenRegistry={() => setView("registry")}
      />
    );
  }

  // Администратор
  if (isAdmin) {
    if (view === "registry") {
      return <RegistryApp user={user} onLogout={logout} onBack={() => setView("home")} />;
    }
    return <AdminApp user={user} onLogout={logout} onOpenRegistry={() => setView("registry")} />;
  }

  // Полевые роли (мастер/прораб)
  if (isField) {
    return <FieldApp user={user} online={online} onLogout={logout} />;
  }

  return (
    <div className="page">
      <p className="error">Для вашей роли интерфейс пока не открыт.</p>
      <button type="button" onClick={logout}>Выйти</button>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
