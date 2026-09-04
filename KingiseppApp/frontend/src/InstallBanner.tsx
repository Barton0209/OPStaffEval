import { useEffect, useState } from "react";

type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

/**
 * Ярлык на домашний экран с иконкой приложения.
 * Android не позволяет ставить ярлык совсем без нажатия — нужен один тап.
 */
export function InstallBanner() {
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null);
  const [hidden, setHidden] = useState(() => localStorage.getItem("kingisepp_hide_install") === "1");
  const [hint, setHint] = useState(false);
  const [installed, setInstalled] = useState(
    () => window.matchMedia("(display-mode: standalone)").matches || (navigator as Navigator & { standalone?: boolean }).standalone === true,
  );

  useEffect(() => {
    const onBip = (e: Event) => {
      e.preventDefault();
      setDeferred(e as BeforeInstallPromptEvent);
    };
    const onInstalled = () => {
      setInstalled(true);
      setDeferred(null);
      localStorage.setItem("kingisepp_hide_install", "1");
    };
    window.addEventListener("beforeinstallprompt", onBip);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onBip);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  if (installed || hidden) return null;

  async function install() {
    if (deferred) {
      await deferred.prompt();
      const choice = await deferred.userChoice;
      if (choice.outcome === "accepted") {
        setInstalled(true);
        localStorage.setItem("kingisepp_hide_install", "1");
      }
      setDeferred(null);
      return;
    }
    setHint(true);
  }

  function dismiss() {
    localStorage.setItem("kingisepp_hide_install", "1");
    setHidden(true);
  }

  return (
    <div className="install-banner" role="region" aria-label="Установка ярлыка">
      <img src="./icon-192.png" alt="" width={48} height={48} className="install-logo" />
      <div className="install-text">
        <strong>Ярлык «Оценка ОП» на экран</strong>
        <span className="muted">
          Один раз нажмите кнопку — появится иконка с нашим знаком, как у обычного приложения.
        </span>
        {hint && (
          <span className="muted">
            Если кнопка не сработала: в меню браузера (⋮) выберите «На экран Домой» / «Установить приложение».
          </span>
        )}
      </div>
      <div className="install-actions">
        <button type="button" className="primary" onClick={install}>
          Установить
        </button>
        <button type="button" className="ghost" onClick={dismiss}>
          Позже
        </button>
      </div>
    </div>
  );
}
