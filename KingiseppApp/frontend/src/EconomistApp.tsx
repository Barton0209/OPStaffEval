import { useEffect, useState } from "react";
import { apiEconomistMissingRates, type SessionUser } from "./api";
import { EconomistPanel } from "./admin/EconomistPanel";

type Props = {
    user: SessionUser;
    onLogout: () => void;
};

/** ЛК экономиста: ведение ЧТС, история, контроль незаполненных ставок. */
export function EconomistApp({ user, onLogout }: Props) {
    const [missingCount, setMissingCount] = useState(0);

    useEffect(() => {
        apiEconomistMissingRates()
            .then((r) => setMissingCount(r.count))
            .catch(() => undefined);
    }, []);

    return (
        <div className="page">
            <div className="app-topbar">
                <div className="app-brandline">
                    <b>{user.fio}</b>
                    <span className="muted"> · Экономист · ведение ЧТС</span>
                </div>
                <div className="app-topbar-actions">
                    {missingCount > 0 && (
                        <span className="badge-bell" title={`Сотрудников без ЧТС: ${missingCount}`}>
                            ⚙ {missingCount}
                        </span>
                    )}
                    <button type="button" className="pill ghost" onClick={onLogout}>
                        Выйти
                    </button>
                </div>
            </div>
            <main className="economist-body">
                <EconomistPanel />
            </main>
        </div>
    );
}