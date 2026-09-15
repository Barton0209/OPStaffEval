import type { EventRow } from "./common";

type Props = {
    events: EventRow[];
};

export function EventsPanel({ events }: Props) {
    return (
        <section className="panel">
            <h2>Журнал действий</h2>
            <div className="excel-wrap tall">
                <table className="excel-table">
                    <thead>
                        <tr>
                            <th>Когда</th>
                            <th>Объект</th>
                            <th>id</th>
                            <th>Действие</th>
                        </tr>
                    </thead>
                    <tbody>
                        {events.map((e) => (
                            <tr key={e.id}>
                                <td>{e.created_at}</td>
                                <td>{e.entity_type}</td>
                                <td>{e.entity_id}</td>
                                <td>{e.action}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </section>
    );
}