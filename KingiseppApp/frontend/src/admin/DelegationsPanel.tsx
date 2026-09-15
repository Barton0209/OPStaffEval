import type { AdminUser } from "../api";
import type { DelegationRow } from "./common";

type Props = {
    masters: AdminUser[];
    delegations: DelegationRow[];
    orig: string;
    onOrig: (v: string) => void;
    sub: string;
    onSub: (v: string) => void;
    from: string;
    onFrom: (v: string) => void;
    to: string;
    onTo: (v: string) => void;
    busy: boolean;
    onMasterName: (id: number) => string;
    onCreate: () => void;
    onDeactivate: (id: number) => void;
};

export function DelegationsPanel({
    masters,
    delegations,
    orig,
    onOrig,
    sub,
    onSub,
    from,
    onFrom,
    to,
    onTo,
    busy,
    onMasterName,
    onCreate,
    onDeactivate,
}: Props) {
    return (
        <section className="panel">
            <h2>Замещение</h2>
            <div className="row">
                <select value={orig} onChange={(e) => onOrig(e.target.value)}>
                    <option value="">Кого замещаем…</option>
                    {masters.map((m) => (
                        <option key={m.id} value={m.id}>
                            {m.fio}
                        </option>
                    ))}
                </select>
                <select value={sub} onChange={(e) => onSub(e.target.value)}>
                    <option value="">Кто замещает…</option>
                    {masters.map((m) => (
                        <option key={m.id} value={m.id}>
                            {m.fio}
                        </option>
                    ))}
                </select>
                <input type="date" value={from} onChange={(e) => onFrom(e.target.value)} />
                <input type="date" value={to} onChange={(e) => onTo(e.target.value)} />
                <button
                    type="button"
                    className="primary"
                    disabled={busy || !orig || !sub || !from || !to || orig === sub}
                    onClick={() => void onCreate()}
                >
                    Создать
                </button>
            </div>
            <div className="excel-wrap">
                <table className="excel-table">
                    <thead>
                        <tr>
                            <th>Кого</th>
                            <th>Кто замещает</th>
                            <th>С</th>
                            <th>По</th>
                            <th>Статус</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>
                        {delegations.map((d) => (
                            <tr key={d.id}>
                                <td>{onMasterName(d.original_user_id)}</td>
                                <td>{onMasterName(d.substitute_user_id)}</td>
                                <td>{d.starts_on}</td>
                                <td>{d.ends_on}</td>
                                <td>{d.is_active ? "действует" : "снято"}</td>
                                <td>
                                    {d.is_active && (
                                        <button type="button" onClick={() => void onDeactivate(d.id)}>
                                            Снять
                                        </button>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </section>
    );
}