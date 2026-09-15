import { useEffect, useState, type RefObject } from "react";
import type { AdminUser } from "../api";
import { ExcelSheet, type ExcelColumn } from "../ExcelSheet";
import { ROLE_LABELS, type NewUserDraft, type SettingsSub, type UserDraft } from "./common";

function TariffGridUpload({
    busy,
    onUpload,
}: {
    busy: boolean;
    onUpload: (f: File) => void;
}) {
    const [file, setFile] = useState<File | null>(null);
    return (
        <div className="row">
            <input
                type="file"
                accept=".xlsx,.xls"
                aria-label="Файл тарифной сетки"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
            {file && <span className="ok-text">{file.name}</span>}
            <button
                type="button"
                className="primary"
                disabled={busy || !file}
                onClick={() => file && void onUpload(file)}
            >
                Загрузить тарифную сетку
            </button>
        </div>
    );
}

type Props = {
    sub: SettingsSub;
    onSub: (s: SettingsSub) => void;
    counts: { masters: number; chiefs: number };
    fileBase: File | null;
    onFileBase: (f: File | null) => void;
    fileUsers: File | null;
    onFileUsers: (f: File | null) => void;
    fileCarnet: File | null;
    onFileCarnet: (f: File | null) => void;
    fileUd: File | null;
    onFileUd: (f: File | null) => void;
    fileDaily: File | null;
    onFileDaily: (f: File | null) => void;
    busy: boolean;
    onUpload: () => void;
    onImportFolder: () => void;
    onUploadTariffGrid: (f: File) => void;
    onUploadDaily: (f: File) => void;
    users: AdminUser[];
    userQ: string;
    onUserQ: (v: string) => void;
    userEdits: Record<number, UserDraft>;
    savingUserId: number | null;
    columns: ExcelColumn<AdminUser>[];
    showNewUser: boolean;
    onToggleNewUser: () => void;
    newUser: NewUserDraft;
    onNewUser: (u: NewUserDraft) => void;
    creatingUser: boolean;
    onCreateUser: () => void;
    usersFileRef: RefObject<HTMLInputElement | null>;
    onUploadUsersFile: (f: File) => void;
    onReloadUsers: () => void;
};

export function SettingsPanel({
    sub,
    onSub,
    counts,
    fileBase,
    onFileBase,
    fileUsers,
    onFileUsers,
    fileCarnet,
    onFileCarnet,
    fileUd,
    onFileUd,
    fileDaily,
    onFileDaily,
    busy,
    onUpload,
    onImportFolder,
    onUploadTariffGrid,
    onUploadDaily,
    users,
    userQ,
    onUserQ,
    userEdits,
    savingUserId,
    columns,
    showNewUser,
    onToggleNewUser,
    newUser,
    onNewUser,
    creatingUser,
    onCreateUser,
    usersFileRef,
    onUploadUsersFile,
    onReloadUsers,
}: Props) {
    return (
        <section className="panel excel-panel">
            <h2>Настройки</h2>

            <div className="assign-view-tabs">
                <button
                    type="button"
                    className={sub === "admin_imports" ? "active" : ""}
                    onClick={() => onSub("admin_imports")}
                >
                    Загрузка файлов (Администрация)
                </button>
                <button
                    type="button"
                    className={sub === "economist_imports" ? "active" : ""}
                    onClick={() => onSub("economist_imports")}
                >
                    Загрузка файлов (Экономисты)
                </button>
                <button
                    type="button"
                    className={sub === "masters" ? "active" : ""}
                    onClick={() => onSub("masters")}
                >
                    Прораб / Мастер · {counts.masters}
                </button>
                <button
                    type="button"
                    className={sub === "chiefs" ? "active" : ""}
                    onClick={() => onSub("chiefs")}
                >
                    Начальник участка и др. · {counts.chiefs}
                </button>
                <button
                    type="button"
                    className={sub === "fired" ? "active" : ""}
                    onClick={() => onSub("fired")}
                >
                    Архив уволенных
                </button>
            </div>

            {sub === "import" && (
                <>
                    <p className="muted">
                        Отдел мобилизации загружает три файла: база 1С, пользователи и{" "}
                        <strong>03_Реестр_закрепления.xlsx</strong> (кто за каким прорабом/мастером). Реестр закрепления —
                        долгоживущий: достаточно загрузить при старте или при изменении; пока не поменяете — человек
                        остаётся за тем же оценщиком (год и дольше). Смотреть список: вкладка «Закрепление».
                    </p>

                    <div className="upload-grid">
                        <label className="upload-card">
                            <strong>1. База 1С</strong>
                            <span className="muted">файл 01_База_1С.xlsx</span>
                            <input
                                type="file"
                                accept=".xlsx,.xls"
                                onChange={(e) => onFileBase(e.target.files?.[0] || null)}
                            />
                            {fileBase && <span className="ok-text">{fileBase.name}</span>}
                        </label>
                        <label className="upload-card">
                            <strong>2. Пользователи</strong>
                            <span className="muted">файл 02_Пользователи.xlsx</span>
                            <input
                                type="file"
                                accept=".xlsx,.xls"
                                onChange={(e) => onFileUsers(e.target.files?.[0] || null)}
                            />
                            {fileUsers && <span className="ok-text">{fileUsers.name}</span>}
                        </label>
                        <label className="upload-card">
                            <strong>3. Реестр закрепления</strong>
                            <span className="muted">файл 03_Реестр_закрепления.xlsx</span>
                            <input
                                type="file"
                                accept=".xlsx,.xls"
                                onChange={(e) => onFileCarnet(e.target.files?.[0] || null)}
                            />
                            {fileCarnet && <span className="ok-text">{fileCarnet.name}</span>}
                        </label>
                        <label className="upload-card">
                            <strong>4. УД список / ЧТС</strong>
                            <span className="muted">файл УД_Список сотрудников (.xlsb)</span>
                            <input
                                type="file"
                                accept=".xlsb,.xlsx"
                                onChange={(e) => onFileUd(e.target.files?.[0] || null)}
                            />
                            {fileUd && <span className="ok-text">{fileUd.name}</span>}
                        </label>
                    </div>

                    <div className="row" style={{ marginTop: "1rem" }}>
                        <button
                            type="button"
                            className="primary"
                            disabled={busy || (!fileBase && !fileUsers && !fileCarnet && !fileUd)}
                            onClick={() => void onUpload()}
                        >
                            {busy ? "Загрузка…" : "Загрузить выбранные файлы"}
                        </button>
                        <button type="button" disabled={busy} onClick={() => void onImportFolder()}>
                            Импорт из папки Files на сервере
                        </button>
                    </div>
                    <p className="muted" style={{ marginTop: "0.75rem" }}>
                        После загрузки данные сразу попадают в назначения, базу и пользователей. Можно повторять импорт —
                        строки обновятся.
                    </p>

                    <div className="panel tariff-grid-block" style={{ marginTop: "1rem" }}>
                        <h3>Тарифная сетка (мин/макс ЧТС)</h3>
                        <p className="muted" style={{ margin: 0 }}>
                            Файл <strong>Сводная_тарифная_сетка.xlsx</strong>: вилка по должности и гражданству.
                            Используется для проверки, выходит ли ЧТС сотрудника за рамки сетки. Доступно только
                            ADMIN-OP.
                        </p>
                        <TariffGridUpload busy={busy} onUpload={onUploadTariffGrid} />
                    </div>

                    <div className="panel tariff-grid-block" style={{ marginTop: "1rem" }}>
                        <h3>5. Ежедневная выгрузка</h3>
                        <p className="muted" style={{ margin: 0 }}>
                            Упрощённый импорт одним файлом Excel: колонки «Табельный номер», «ФИО», «Должность»,
                            «Участок», «Прораб/Мастер». Сотрудники находятся по табельному номеру; у кого указан
                            прораб/мастер — перезакрепляются на него. Пустые строки и неизвестные табельные
                            пропускаются.
                        </p>
                        <div className="row" style={{ marginTop: "0.75rem" }}>
                            <input
                                type="file"
                                accept=".xlsx,.xls"
                                aria-label="Файл ежедневной выгрузки"
                                onChange={(e) => onFileDaily(e.target.files?.[0] || null)}
                            />
                            {fileDaily && <span className="ok-text">{fileDaily.name}</span>}
                            <button
                                type="button"
                                className="primary"
                                disabled={busy || !fileDaily}
                                onClick={() => fileDaily && void onUploadDaily(fileDaily)}
                            >
                                {busy ? "Импорт…" : "Импортировать выгрузку"}
                            </button>
                        </div>
                    </div>
                </>
            )}

            {sub === "admin_imports" && (
                <AdminImportsPanel
                    busy={busy}
                    onUpload={onUpload}
                />
            )}

            {sub === "economist_imports" && (
                <EconomistImportsPanel
                    busy={busy}
                    onUploadTariffGrid={onUploadTariffGrid}
                />
            )}

            {sub === "fired" && <FiredPanel />}

            {sub !== "import" && sub !== "admin_imports" && sub !== "economist_imports" && sub !== "fired" && (
                <>
                    <p className="muted" style={{ marginTop: 0 }}>
                        {sub === "masters"
                            ? "Пользователи с ролью «Мастер» или «Производитель работ» из файла 02_Пользователи.xlsx."
                            : "Начальники участков и остальные пользователи из файла 02_Пользователи.xlsx."}{" "}
                        Правьте роль, участок, статус или пароль и нажимайте «Сохранить» в строке. Пустое поле пароля — не
                        менять.
                    </p>
                    <div className="excel-toolbar">
                        <input
                            placeholder="Поиск: ФИО / таб.№ / участок"
                            value={userQ}
                            onChange={(e) => onUserQ(e.target.value)}
                        />
                        <button
                            type="button"
                            className="primary"
                            onClick={() => {
                                onToggleNewUser();
                                onNewUser({ ...newUser, role: sub === "masters" ? "master" : "site_chief" });
                            }}
                        >
                            {showNewUser ? "✕ Отмена" : "+ Создать сотрудника"}
                        </button>
                        <button type="button" disabled={busy} onClick={() => usersFileRef.current?.click()}>
                            ⬆ Загрузить из файла
                        </button>
                        <input
                            ref={usersFileRef}
                            type="file"
                            accept=".xlsx,.xls"
                            style={{ display: "none" }}
                            onChange={(e) => {
                                const f = e.target.files?.[0];
                                if (f) void onUploadUsersFile(f);
                            }}
                        />
                        <button type="button" onClick={() => void onReloadUsers()}>
                            Обновить
                        </button>
                        <span className="muted">
                            На экране: <strong>{users.length}</strong>
                            {Object.keys(userEdits).length
                                ? ` · изменено строк: ${Object.keys(userEdits).length}`
                                : ""}
                        </span>
                    </div>
                    {showNewUser && (
                        <div className="row panel new-user-form">
                            <input
                                placeholder="Таб. № *"
                                value={newUser.tab_no}
                                onChange={(e) => onNewUser({ ...newUser, tab_no: e.target.value })}
                                style={{ width: 130 }}
                            />
                            <input
                                placeholder="ФИО *"
                                value={newUser.fio}
                                onChange={(e) => onNewUser({ ...newUser, fio: e.target.value })}
                                style={{ minWidth: 220 }}
                            />
                            <select
                                value={newUser.role}
                                onChange={(e) => onNewUser({ ...newUser, role: e.target.value })}
                                aria-label="Роль"
                            >
                                {Object.entries(ROLE_LABELS).map(([val, label]) => (
                                    <option key={val} value={val}>
                                        {label}
                                    </option>
                                ))}
                            </select>
                            <input
                                placeholder="Код участка"
                                value={newUser.site_code}
                                onChange={(e) => onNewUser({ ...newUser, site_code: e.target.value })}
                                style={{ width: 110 }}
                            />
                            <input
                                placeholder="Участок"
                                value={newUser.site_name}
                                onChange={(e) => onNewUser({ ...newUser, site_name: e.target.value })}
                                style={{ width: 170 }}
                            />
                            <select
                                value={newUser.status}
                                onChange={(e) => onNewUser({ ...newUser, status: e.target.value })}
                                aria-label="Статус"
                            >
                                <option value="Активен">Активен</option>
                                <option value="Отключен">Отключен</option>
                            </select>
                            <input
                                type="password"
                                autoComplete="new-password"
                                placeholder="Пароль *"
                                value={newUser.password}
                                onChange={(e) => onNewUser({ ...newUser, password: e.target.value })}
                                style={{ width: 120 }}
                            />
                            <button type="button" className="primary" disabled={creatingUser} onClick={() => void onCreateUser()}>
                                {creatingUser ? "Создаю…" : "Создать"}
                            </button>
                        </div>
                    )}
                    <ExcelSheet
                        rows={users}
                        columns={columns}
                        rowKey={(u) => u.id}
                        defaultRowHeight={36}
                        emptyText="Нет пользователей в этой группе."
                    />
                </>
            )}
        </section>
    );
}

// ==================== Новые компоненты ====================

const ADMIN_BLOCKS = [
    { name: "1. База сотрудников", key: "База сотрудников", desc: "01_Base — столбцы A,B,E-G,I,K-N" },
    { name: "2. Ежедневный учет", key: "Ежедневный учет", desc: "02_Daily — строка 5 заголовок, строка 6 данные" },
    { name: "3. Пользователи, роли, доступ", key: "Пользователи, роли, доступ", desc: "03_Users — 3 листа: Group_of_Users, Users, Прораб_Мастер" },
];

const REGISTRY_SLOTS = [
    { label: "2024 Реестр за 1 полугодие", slot: "2024 1 полугодие" },
    { label: "2024 Реестр за 2 полугодие", slot: "2024 2 полугодие" },
    { label: "2025 Реестр за 1 полугодие", slot: "2025 1 полугодие" },
    { label: "2025 Реестр за 2 полугодие", slot: "2025 2 полугодие" },
    { label: "2026 Реестр за 1 полугодие", slot: "2026 1 полугодие" },
    { label: "2026 Реестр за 2 полугодие", slot: "2026 2 полугодие" },
];

function AdminImportsPanel({ busy, onUpload }: { busy: boolean; onUpload: () => void }) {
    const [files, setFiles] = useState<Record<string, File | null>>({});
    const [registryFiles, setRegistryFiles] = useState<Record<string, File | null>>({});
    const [results, setResults] = useState<Record<string, any>>({});
    const [log, setLog] = useState<any[]>([]);

    // Загружаем журнал импортов
    useEffect(() => {
        (async () => {
            try {
                const token = localStorage.getItem("kingisepp_token");
                const res = await fetch("/api/admin/import-log", {
                    headers: { Authorization: `Bearer ${token || ""}` },
                });
                if (res.ok) setLog(await res.json());
            } catch { /* ignore */ }
        })();
    }, []);

    async function handleUpload(block: string, slot?: string) {
        const file = slot ? registryFiles[slot] : files[block];
        if (!file) return;
        setBusy(true);
        try {
            const formData = new FormData();
            formData.append("block", block);
            if (slot) formData.append("slot", slot);
            formData.append("file", file);
            const res = await fetch(`/api/admin/import/upload?block=${encodeURIComponent(block)}${slot ? `&slot=${encodeURIComponent(slot)}` : ""}`, {
                method: "POST",
                body: formData,
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "Ошибка");
            setResults((r) => ({ ...r, [slot || block]: data.result }));
            // Обновляем журнал
            setLog((prev) => [{
                block_name: block,
                slot_name: slot,
                file_name: file.name,
                uploaded_at: new Date().toLocaleString("ru-RU"),
                added: data.result.added,
                updated: data.result.updated,
                errors_count: data.result.errors?.length || 0,
                success: data.result.errors?.length === 0,
            }, ...prev]);
        } catch (e) {
            alert(e instanceof Error ? e.message : "Ошибка загрузки");
        } finally {
            setBusy(false);
        }

    return (
        <div className="panel">
            <h3>Загрузка файлов с данными (Администрация)</h3>

            {/* Блоки 1-3 */}
            <div className="upload-grid">
                {ADMIN_BLOCKS.map((block) => (
                    <div key={block.key} className="upload-card">
                        <strong>{block.name}</strong>
                        <span className="muted" style={{ fontSize: 0.8 }}>{block.desc}</span>
                        <input
                            type="file"
                            accept=".xlsx,.xls"
                            onChange={(e) => setFiles((f) => ({ ...f, [block.key]: e.target.files?.[0] || null }))}
                            style={{ marginTop: 8 }}
                        />
                        {files[block.key] && (
                            <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 4 }}>
                                <span className="ok-text" style={{ fontSize: 0.8 }}>{files[block.key]!.name}</span>
                                <button
                                    type="button"
                                    className="primary"
                                    disabled={busy || !files[block.key]}
                                    onClick={() => handleUpload(block.key)}
                                    style={{ fontSize: 0.75, padding: "3px 10px" }}
                                >
                                    Загрузить
                                </button>
                            </div>
                        )}
                        {results[block.key] && (
                            <div style={{ fontSize: 0.8, marginTop: 4 }}>
                                ✅ +{results[block.key].added} обнов:{results[block.key].updated}
                                {results[block.key].errors?.length > 0 && (
                                    <span style={{ color: "#dc2626", marginLeft: 8 }}>⚠ Ошибок: {results[block.key].errors.length}</span>
                                )}
                            </div>
                        )}
                    </div>
                ))}
            </div>

            {/* Блок 4 — Реестры оценок */}
            <div style={{ marginTop: 20 }}>
                <h4 style={{ margin: "0 0 12px", color: "#2563eb" }}>📋 4. Реестры оценок (12 критериев × 2 оценщика)</h4>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 12 }}>
                    {REGISTRY_SLOTS.map(({ label, slot }) => {
                        const hasFile = !!registryFiles[slot];
                        const result = results[slot];
                        return (
                            <div key={slot} className="upload-card" style={{ border: "1px solid #e0e7ff" }}>
                                <strong style={{ color: "#2563eb" }}>{label}</strong>
                                <input
                                    type="file"
                                    accept=".xlsx"
                                    onChange={(e) => setRegistryFiles((f) => ({ ...f, [slot]: e.target.files?.[0] || null }))}
                                    style={{ marginTop: 6 }}
                                />
                                {hasFile && (
                                    <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 4 }}>
                                        <span className="ok-text" style={{ fontSize: 0.75 }}>{registryFiles[slot]!.name}</span>
                                        <button
                                            type="button"
                                            className="primary"
                                            disabled={busy || !hasFile}
                                            onClick={() => handleUpload("Реестры оценок", slot)}
                                            style={{ fontSize: 0.75, padding: "3px 10px" }}
                                        >
                                            Загрузить
                                        </button>
                                    </div>
                                )}
                                {result && (
                                    <div style={{ fontSize: 0.8, marginTop: 4 }}>
                                        ✅ +{result.added} обнов:{result.updated}
                                        {result.errors?.length > 0 && (
                                            <span style={{ color: "#dc2626", marginLeft: 8 }}>⚠ {result.errors.length} ош.</span>
                                        )}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Журнал импортов */}
            {log.length > 0 && (
                <div style={{ marginTop: 20 }}>
                    <h4 style={{ margin: "0 0 8px" }}>📜 Журнал загрузок</h4>
                    <div style={{ maxHeight: 200, overflowY: "auto" }}>
                        {log.map((entry, i) => (
                            <div key={i} style={{
                                padding: "6px 10px",
                                borderBottom: "1px solid #eee",
                                fontSize: 0.8,
                                background: entry.success ? "#f0fdf4" : "#fef2f2",
                            }}>
                                <strong>{entry.block_name}</strong>
                                {entry.slot_name && <span style={{ color: "#666" }}> — {entry.slot_name}</span>}
                                <span style={{ color: "#888", marginLeft: 8 }}>{entry.file_name}</span>
                                <span style={{ color: "#888", marginLeft: 8 }}>{entry.uploaded_at}</span>
                                <span style={{ marginLeft: 8 }}>✅ +{entry.added} обнов:{entry.updated}</span>
                                {entry.errors_count > 0 && (
                                    <span style={{ color: "#dc2626", marginLeft: 8 }}>⚠ {entry.errors_count} ош.</span>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}


            <h3>Загрузка файлов с данными (Администрация)</h3>

            {/* Блоки 1-3 */}
            <div className="upload-grid">
                {ADMIN_BLOCKS.map((block) => (
                    <div key={block.key} className="upload-card">
                        <strong>{block.name}</strong>
                        <span className="muted" style={{ fontSize: 0.8 }}>{block.desc}</span>
                        <input
                            type="file"
                            accept=".xlsx,.xls"
                            onChange={(e) => setFiles((f) => ({ ...f, [block.key]: e.target.files?.[0] || null }))}
                            style={{ marginTop: 8 }}
                        />
                        {files[block.key] && (
                            <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 4 }}>
                                <span className="ok-text" style={{ fontSize: 0.8 }}>{files[block.key]!.name}</span>
                                <button
                                    type="button"
                                    className="primary"
                                    disabled={busy || !files[block.key]}
                                    onClick={() => handleUpload(block.key)}
                                    style={{ fontSize: 0.75, padding: "3px 10px" }}
                                >
                                    Загрузить
                                </button>
                            </div>
                        )}
                        {results[block.key] && (
                            <div style={{ fontSize: 0.8, marginTop: 4 }}>
                                ✅ +{results[block.key].added} обнов:{results[block.key].updated}
                                {results[block.key].errors?.length > 0 && (
                                    <span style={{ color: "#dc2626", marginLeft: 8 }}>⚠ Ошибок: {results[block.key].errors.length}</span>
                                )}
                            </div>
                        )}
                    </div>
                ))}
            </div>

            {/* Блок 4 — Реестры оценок */}
            <div style={{ marginTop: 20 }}>
                <h4 style={{ margin: "0 0 12px", color: "#2563eb" }}>📋 4. Реестры оценок (12 критериев × 2 оценщика)</h4>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 12 }}>
                    {REGISTRY_SLOTS.map(({ label, slot }) => {
                        const hasFile = !!registryFiles[slot];
                        const result = results[slot];
                        return (
                            <div key={slot} className="upload-card" style={{ border: "1px solid #e0e7ff" }}>
                                <strong style={{ color: "#2563eb" }}>{label}</strong>
                                <input
                                    type="file"
                                    accept=".xlsx"
                                    onChange={(e) => setRegistryFiles((f) => ({ ...f, [slot]: e.target.files?.[0] || null }))}
                                    style={{ marginTop: 6 }}
                                />
                                {hasFile && (
                                    <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 4 }}>
                                        <span className="ok-text" style={{ fontSize: 0.75 }}>{registryFiles[slot]!.name}</span>
                                        <button
                                            type="button"
                                            className="primary"
                                            disabled={busy || !hasFile}
                                            onClick={() => handleUpload("Реестры оценок", slot)}
                                            style={{ fontSize: 0.75, padding: "3px 10px" }}
                                        >
                                            Загрузить
                                        </button>
                                    </div>
                                )}
                                {result && (
                                    <div style={{ fontSize: 0.8, marginTop: 4 }}>
                                        ✅ +{result.added} обнов:{result.updated}
                                        {result.errors?.length > 0 && (
                                            <span style={{ color: "#dc2626", marginLeft: 8 }}>⚠ {result.errors.length} ош.</span>
                                        )}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Журнал импортов */}
            {log.length > 0 && (
                <div style={{ marginTop: 20 }}>
                    <h4 style={{ margin: "0 0 8px" }}>📜 Журнал загрузок</h4>
                    <div style={{ maxHeight: 200, overflowY: "auto" }}>
                        {log.map((entry, i) => (
                            <div key={i} style={{
                                padding: "6px 10px",
                                borderBottom: "1px solid #eee",
                                fontSize: 0.8,
                                background: entry.success ? "#f0fdf4" : "#fef2f2",
                            }}>
                                <strong>{entry.block_name}</strong>
                                {entry.slot_name && <span style={{ color: "#666" }}> — {entry.slot_name}</span>}
                                <span style={{ color: "#888", marginLeft: 8 }}>{entry.file_name}</span>
                                <span style={{ color: "#888", marginLeft: 8 }}>{entry.uploaded_at}</span>
                                <span style={{ marginLeft: 8 }}>✅ +{entry.added} обнов:{entry.updated}</span>
                                {entry.errors_count > 0 && (
                                    <span style={{ color: "#dc2626", marginLeft: 8 }}>⚠ {entry.errors_count} ош.</span>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

function EconomistImportsPanel({ busy, onUploadTariffGrid }: { busy: boolean; onUploadTariffGrid: (f: File) => void }) {
    const [fileUd, setFileUd] = useState<File | null>(null);
    const [fileTariff, setFileTariff] = useState<File | null>(null);
    return (
        <div className="panel">
            <h3>Загрузка файлов с данными (Экономисты)</h3>
            <div className="upload-grid">
                <label className="upload-card">
                    <strong>УД список / ЧТС</strong>
                    <span className="muted">файл УД_Список сотрудников (.xlsb)</span>
                    <input
                        type="file"
                        accept=".xlsb,.xlsx"
                        onChange={(e) => setFileUd(e.target.files?.[0] || null)}
                    />
                    {fileUd && <span className="ok-text">{fileUd.name}</span>}
                </label>
                <label className="upload-card">
                    <strong>Тарифная сетка (мин/макс ЧТС)</strong>
                    <span className="muted">файл Сводная_тарифная_сетка.xlsx</span>
                    <input
                        type="file"
                        accept=".xlsx"
                        onChange={(e) => setFileTariff(e.target.files?.[0] || null)}
                    />
                    {fileTariff && <span className="ok-text">{fileTariff.name}</span>}
                    <button
                        type="button"
                        className="primary"
                        disabled={busy || !fileTariff}
                        onClick={() => fileTariff && onUploadTariffGrid(fileTariff)}
                        style={{ marginTop: 8 }}
                    >
                        Загрузить тарифную сетку
                    </button>
                </label>
            </div>
        </div>
    );
}

function FiredPanel() {
    const [fired, setFired] = useState<any[]>([]);
    const [search, setSearch] = useState("");

    useEffect(() => {
        (async () => {
            try {
                const url = search ? `/api/admin/fired?search=${encodeURIComponent(search)}` : "/api/admin/fired";
                setFired(await (await fetch(url, { headers: { Authorization: `Bearer ${localStorage.getItem("kingisepp_token")}` } })).json());
            } catch (e) { /* ignore */ }
        })();
    }, [search]);

    return (
        <div className="panel">
            <h3>Архив уволенных</h3>
            <input
                placeholder="Поиск: ФИО / таб.№"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ marginBottom: 12 }}
            />
            <button
                type="button"
                className="primary"
                onClick={() => {
                    const token = localStorage.getItem("kingisepp_token");
                    window.open(`/api/admin/fired/export.xlsx?_token=${token}`, "_blank");
                }}
            >
                Выгрузить Excel
            </button>
            <div style={{ marginTop: 12 }}>
                <p>Найдено: {fired.length}</p>
                {fired.map((f) => (
                    <div key={f.id} style={{ padding: 8, borderBottom: "1px solid #eee" }}>
                        <strong>{f.fio}</strong> ({f.tab_no}) — {f.position_1c || "без должности"}
                        <br />
                        <span className="muted">
                            Приём: {f.hire_date || "—"} | Увольнение: {f.fire_date || "—"} | Статус: {f.state || "—"}
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
}