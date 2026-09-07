import { useEffect, useMemo, useRef, useState } from "react";
import {
  apiAdminAssignments,
  apiAssignSecondary,
  apiBulkAssignments,
  apiCloseUrgent,
  apiCreateDelegation,
  apiCreateEmployee,
  apiCreateUrgent,
  apiCreateUser,
  apiDashboard,
  apiDeactivateDelegation,
  apiDelegations,
  apiEmployees,
  apiEscalations,
  apiEvents,
  apiFormalizeCandidate,
  apiImportAll,
  apiImportUpload,
  apiListUrgent,
  apiPatchTicket,
  apiPatchUser,
  apiSecondEvaluation,
  apiTickets,
  apiUsers,
  type AdminAssignment,
  type AdminEmployee,
  type AdminUser,
  type Dashboard,
  type SecondEvalRow,
  type SessionUser,
  type Ticket,
} from "./api";

import { ExcelSheet, type ExcelColumn } from "./ExcelSheet";

type Tab =
  | "dash"
  | "assign"
  | "second"
  | "urgent"
  | "delegate"
  | "employees"
  | "tickets"
  | "events"
  | "settings";

type SettingsSub = "import" | "masters" | "chiefs";

type SecondGroup = "all" | "no_evaluators" | "no_secondary" | "on_first" | "got_first";

type UserDraft = {
  role: string;
  site_code: string;
  site_name: string;
  status: string;
  password: string;
};

const ROLE_LABELS: Record<string, string> = {
  master: "Мастер",
  foreman: "Производитель работ",
  site_chief: "Начальник участка",
  admin_op: "Администрация ОП",
  admin: "Админ",
};

const ROLE_ORDER = ["master", "foreman", "site_chief", "admin_op", "admin"];

function roleLabel(role: string) {
  return ROLE_LABELS[role] || role;
}

/** Нормализация для сравнения участков */
function nfSite(s?: string | null) {
  return (s || "").trim().toLowerCase().replace(/\s+/g, " ");
}

function evalStatusLabel(st: SecondEvalRow["primary_eval_status"]) {
  return st === "submitted" ? "сдана" : st === "draft" ? "в работе" : "не начата";
}

const SECOND_GROUPS: { id: SecondGroup; label: string; match: (r: SecondEvalRow) => boolean }[] = [
  { id: "all", label: "Все сотрудники", match: () => true },
  {
    id: "no_evaluators",
    label: "Без 1 и 2 оценщика",
    match: (r) => !r.primary_user_id && !(r.dual_enabled && r.secondary_user_id),
  },
  {
    id: "no_secondary",
    label: "Без 2 оценщика",
    match: (r) => !!r.primary_user_id && !(r.dual_enabled && r.secondary_user_id),
  },
  {
    id: "on_first",
    label: "На 1 оценке",
    match: (r) => !!r.primary_user_id && r.primary_eval_status !== "submitted",
  },
  {
    id: "got_first",
    label: "Получили 1 оценку",
    match: (r) => !!r.primary_user_id && r.primary_eval_status === "submitted",
  },
];

type Props = {
  user: SessionUser;
  onLogout: () => void;
  onOpenRegistry: () => void;
};

/** Фирменные фоны — кроссфейд-слайдшоу */
const BG_IMAGES = [
  "./brand/bg-1.png",
  "./brand/bg-2.png",
  "./brand/bg-3.png",
  "./brand/bg-4.png",
];


/** Карточка сводки со всплывающей подсказкой при наведении */
function DashCard({
  cls,
  icon,
  label,
  value,
  hint,
  tipTitle,
  tip,
  onClick,
}: {
  cls: string;
  icon: string;
  label: string;
  value: number;
  hint: string;
  tipTitle: string;
  tip: string;
  onClick: () => void;
}) {
  return (
    <button type="button" className={`metric clickable ${cls}`.trim()} onClick={onClick}>
      <div className="metric-ico" aria-hidden>{icon}</div>
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      <div className="hint">{hint}</div>
      <span className="metric-tip" role="tooltip">
        <strong>{tipTitle}</strong>
        <span>{tip}</span>
      </span>
    </button>
  );
}

const TABS: { id: Tab; label: string; tipTitle: string; tip: string }[] = [
  {
    id: "dash",
    label: "Сводка",
    tipTitle: "Сводка",
    tip: "Общая картина периода: сколько людей на оценке, сдано анкет, срочные и обращения.",
  },
  {
    id: "assign",
    label: "Закрепление",
    tipTitle: "Закрепление",
    tip: "Кто за каким прорабом/мастером. Здесь назначают оценщика и отправляют список на оценку.",
  },
  {
    id: "second",
    label: "Вторая оценка",
    tipTitle: "Вторая оценка",
    tip: "Второй независимый оценщик — начальник участка. Назначается только сотрудникам своего участка.",
  },
  {
    id: "urgent",
    label: "Срочная",
    tipTitle: "Срочная оценка",
    tip: "Внеплановая анкета вне общего списка: выбрать сотрудника и оценщиков, открыть/закрыть заявку.",
  },
  {
    id: "delegate",
    label: "Замещение",
    tipTitle: "Замещение",
    tip: "Временная передача списка оценок другому мастеру/прорабу на период отсутствия.",
  },
  {
    id: "employees",
    label: "База",
    tipTitle: "База сотрудников",
    tip: "Справочник людей из 1С и кандидаты: поиск, добавление, оформление кандидата.",
  },
  {
    id: "tickets",
    label: "Обращения",
    tipTitle: "Обращения",
    tip: "Сообщения с площадки об ошибках в списках. Можно ответить и закрыть обращение.",
  },
  {
    id: "events",
    label: "Журнал",
    tipTitle: "Журнал событий",
    tip: "История действий в системе: импорты, назначения, срочные, изменения.",
  },
  {
    id: "settings",
    label: "Настройки",
    tipTitle: "Настройки",
    tip: "Импорт Excel и управление пользователями: роли, участки, статусы, пароли.",
  },
];

function pct(part: number, total: number) {
  if (!total) return 0;
  return Math.round((part / total) * 100);
}

export function AdminApp({ user, onLogout, onOpenRegistry }: Props) {
  const [tab, setTab] = useState<Tab>("dash");
  const [dash, setDash] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);

  // Смена фона — кроссфейд между фирменными фото
  const [bgIndex, setBgIndex] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => {
      setBgIndex((i) => (i + 1) % BG_IMAGES.length);
    }, 7000);
    return () => window.clearInterval(id);
  }, []);

  const [assignments, setAssignments] = useState<AdminAssignment[]>([]);
  const [assignQ, setAssignQ] = useState("");
  const [masters, setMasters] = useState<AdminUser[]>([]);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  /** Один выбор: и фильтр таблицы, и кому назначаем отмеченных */
  const [selectedMasterId, setSelectedMasterId] = useState("");

  const [urgent, setUrgent] = useState<
    {
      id: number;
      fio: string;
      tab_no: string;
      status: string;
      comment: string | null;
      employee_id: number;
      evaluator_names?: string[];
    }[]
  >([]);
  const [urgEmpId, setUrgEmpId] = useState("");
  const [urgEmpQ, setUrgEmpQ] = useState("");
  const [urgEvalIds, setUrgEvalIds] = useState<number[]>([]);
  const [urgEvalQ, setUrgEvalQ] = useState("");
  const [showClosedUrgent, setShowClosedUrgent] = useState(false);
  const [urgComment, setUrgComment] = useState("");
  const [replyDrafts, setReplyDrafts] = useState<Record<number, string>>({});

  const [delegations, setDelegations] = useState<
    {
      id: number;
      original_user_id: number;
      substitute_user_id: number;
      starts_on: string;
      ends_on: string;
      reason: string | null;
      is_active: boolean;
    }[]
  >([]);
  const [delOrig, setDelOrig] = useState("");
  const [delSub, setDelSub] = useState("");
  const [delFrom, setDelFrom] = useState("");
  const [delTo, setDelTo] = useState("");

  const [employees, setEmployees] = useState<AdminEmployee[]>([]);
  const [empQ, setEmpQ] = useState("");
  const [candOnly, setCandOnly] = useState(false);
  const [newTab, setNewTab] = useState("");
  const [newFio, setNewFio] = useState("");
  const [formalizeId, setFormalizeId] = useState("");
  const [formalizeTab, setFormalizeTab] = useState("");

  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [events, setEvents] = useState<
    { id: number; entity_type: string; entity_id: number | null; action: string; created_at: string | null }[]
  >([]);
  const [escalations, setEscalations] = useState<
    {
      user_id: number;
      fio: string;
      tab_no: string;
      pending_assignments: number;
      submitted: number;
      last_login_at: string | null;
    }[]
  >([]);

  const [filterMode, setFilterMode] = useState<"all" | "evaluate" | "with_primary" | "awaiting" | "dual">(
    "with_primary",
  );
  const [visibleAssignRows, setVisibleAssignRows] = useState<AdminAssignment[]>([]);
  const [fileBase, setFileBase] = useState<File | null>(null);
  const [fileUsers, setFileUsers] = useState<File | null>(null);
  const [fileCarnet, setFileCarnet] = useState<File | null>(null);

  // Настройки: пользователи (роли/участки/статусы/пароли)
  const [settingsSub, setSettingsSub] = useState<SettingsSub>("import");
  const [allUsers, setAllUsers] = useState<AdminUser[]>([]);
  const [userEdits, setUserEdits] = useState<Record<number, UserDraft>>({});
  const [savingUserId, setSavingUserId] = useState<number | null>(null);
  const [userQ, setUserQ] = useState("");
  const [showNewUser, setShowNewUser] = useState(false);
  const [creatingUser, setCreatingUser] = useState(false);
  const [newUser, setNewUser] = useState({
    tab_no: "",
    fio: "",
    role: "master",
    site_code: "",
    site_name: "",
    status: "Активен",
    password: "",
  });
  const usersFileRef = useRef<HTMLInputElement>(null);

  // Вторая оценка
  const [secondRows, setSecondRows] = useState<SecondEvalRow[]>([]);
  const [secondGroup, setSecondGroup] = useState<SecondGroup>("no_secondary");
  const [assignMode, setAssignMode] = useState(false);
  const [secondChiefId, setSecondChiefId] = useState("");
  const [secondSel, setSecondSel] = useState<number[]>([]);
  const [chiefs, setChiefs] = useState<AdminUser[]>([]);

  async function loadDash() {
    setDash(await apiDashboard());
    setEscalations(await apiEscalations());
  }

  async function reloadMasters() {
    const [m, f] = await Promise.all([apiUsers("master"), apiUsers("foreman")]);
    setMasters([...m, ...f]);
  }

  async function loadAllUsers() {
    setAllUsers(await apiUsers(undefined, true));
  }

  async function loadSecond() {
    const [rows, ch] = await Promise.all([apiSecondEvaluation(), apiUsers("site_chief")]);
    setSecondRows(rows);
    setChiefs(ch);
  }

  useEffect(() => {
    (async () => {
      try {
        await loadDash();
        await reloadMasters();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Ошибка загрузки");
      }
    })();
  }, []);

  useEffect(() => {
    (async () => {
      setError("");
      try {
        if (tab === "dash") await loadDash();
        if (tab === "assign") {
          setAssignments(await apiAdminAssignments({}));
          setSelectedIds([]);
        }
        if (tab === "second") {
          await loadSecond();
          setSecondSel([]);
        }
        if (tab === "urgent") {
          setUrgent(await apiListUrgent());
          setEmployees(await apiEmployees({}));
        }
        if (tab === "delegate") setDelegations(await apiDelegations());
        if (tab === "employees") {
          setEmployees(await apiEmployees({ q: empQ || undefined, candidates: candOnly }));
        }
        if (tab === "tickets") setTickets(await apiTickets());
        if (tab === "events") setEvents(await apiEvents(80));
        if (tab === "settings") await loadAllUsers();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Ошибка загрузки");
      }
    })();
  }, [tab, candOnly]);

  const progress = useMemo(() => {
    if (!dash) return 0;
    return pct(dash.submitted_evaluations, dash.evaluate_yes || 1);
  }, [dash]);

  const assignStats = useMemo(() => {
    const total = assignments.length;
    const withPrimary = assignments.filter((a) => a.primary_user_id).length;
    const awaiting = assignments.filter((a) => !a.primary_user_id).length;
    const onEval = assignments.filter((a) => a.evaluate).length;
    const dual = assignments.filter((a) => a.dual_enabled).length;
    return { total, withPrimary, awaiting, onEval, dual };
  }, [assignments]);

  const filteredAssignments = useMemo(() => {
    const q = assignQ.trim().toLowerCase();
    return assignments.filter((a) => {
      // В режиме «Без оценщика» список не режем по мастеру — иначе нельзя кого назначить.
      // В остальных режимах выбор прораба/мастера фильтрует таблицу.
      if (selectedMasterId && filterMode !== "awaiting") {
        if (String(a.primary_user_id) !== selectedMasterId) return false;
      }
      if (filterMode === "evaluate" && !a.evaluate) return false;
      if (filterMode === "with_primary" && !a.primary_user_id) return false;
      if (filterMode === "awaiting" && a.primary_user_id) return false;
      if (filterMode === "dual" && !a.dual_enabled) return false;
      if (q) {
        const hay = `${a.fio} ${a.tab_no} ${a.primary_fio || ""} ${a.primary_tab || ""} ${a.site_name || ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [assignments, selectedMasterId, filterMode, assignQ]);

  const masterCounts = useMemo(() => {
    const map = new Map<string, { fio: string; role: string; n: number; userId: number }>();
    for (const a of assignments) {
      if (!a.primary_user_id || !a.primary_fio) continue;
      const key = String(a.primary_user_id);
      const cur = map.get(key) || {
        fio: a.primary_fio,
        role: a.primary_role === "foreman" ? "прораб" : a.primary_role === "master" ? "мастер" : a.primary_role || "",
        n: 0,
        userId: a.primary_user_id,
      };
      cur.n += 1;
      map.set(key, cur);
    }
    return [...map.values()].sort((a, b) => b.n - a.n || a.fio.localeCompare(b.fio, "ru"));
  }, [assignments]);

  const openUrgent = useMemo(() => urgent.filter((u) => u.status === "open"), [urgent]);
  const closedUrgent = useMemo(() => urgent.filter((u) => u.status !== "open"), [urgent]);

  const urgEmpCandidates = useMemo(() => {
    const q = urgEmpQ.trim().toLowerCase();
    return employees
      .filter((e) => {
        if (!q) return true;
        return e.fio.toLowerCase().includes(q) || e.tab_no.toLowerCase().includes(q);
      })
      .slice(0, 60);
  }, [employees, urgEmpQ]);

  const selectedUrgEmp = useMemo(
    () => employees.find((e) => String(e.id) === urgEmpId) || null,
    [employees, urgEmpId],
  );

  const urgMasterCandidates = useMemo(() => {
    const q = urgEvalQ.trim().toLowerCase();
    return masters.filter((m) => {
      if (!q) return true;
      return m.fio.toLowerCase().includes(q) || m.tab_no.toLowerCase().includes(q);
    });
  }, [masters, urgEvalQ]);

  const selectedMaster = useMemo(
    () => masters.find((m) => String(m.id) === selectedMasterId) || null,
    [masters, selectedMasterId],
  );

  // ---------- Настройки: пользователи ----------
  const settingsUsers = useMemo(() => {
    const inMasters = settingsSub === "masters";
    const q = userQ.trim().toLowerCase();
    return allUsers.filter((u) => {
      const isMF = u.role === "master" || u.role === "foreman";
      if (inMasters !== isMF) return false;
      if (q) {
        const hay = `${u.fio} ${u.tab_no} ${u.site_name || ""} ${u.site_code || ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [allUsers, settingsSub, userQ]);

  const settingsCounts = useMemo(() => {
    const mf = allUsers.filter((u) => u.role === "master" || u.role === "foreman").length;
    return { masters: mf, chiefs: allUsers.length - mf };
  }, [allUsers]);

  function userDraft(u: AdminUser): UserDraft {
    return (
      userEdits[u.id] ?? {
        role: u.role,
        site_code: u.site_code ?? "",
        site_name: u.site_name ?? "",
        status: u.status || "Активен",
        password: "",
      }
    );
  }

  function setUserDraft(u: AdminUser, patch: Partial<UserDraft>) {
    setUserEdits((prev) => ({ ...prev, [u.id]: { ...userDraft(u), ...patch } }));
  }

  function userDirty(u: AdminUser): boolean {
    const d = userEdits[u.id];
    if (!d) return false;
    return (
      d.role !== u.role ||
      d.site_code !== (u.site_code ?? "") ||
      d.site_name !== (u.site_name ?? "") ||
      d.status !== (u.status || "Активен") ||
      d.password.trim() !== ""
    );
  }

  async function saveUserRow(u: AdminUser) {
    const d = userEdits[u.id];
    if (!d) return;
    setSavingUserId(u.id);
    setError("");
    try {
      await apiPatchUser(u.id, {
        role: d.role,
        site_code: d.site_code.trim() || null,
        site_name: d.site_name.trim() || null,
        status: d.status,
        ...(d.password.trim() ? { password: d.password.trim() } : {}),
      });
      setUserEdits((prev) => {
        const next = { ...prev };
        delete next[u.id];
        return next;
      });
      await loadAllUsers();
      await reloadMasters();
      setInfo(`Сохранено: ${u.fio}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось сохранить пользователя");
    } finally {
      setSavingUserId(null);
    }
  }

  async function createUser() {
    if (!newUser.tab_no.trim() || !newUser.fio.trim()) {
      setError("Укажите табельный номер и ФИО нового пользователя");
      return;
    }
    if (newUser.password.trim().length < 4) {
      setError("Пароль — минимум 4 символа");
      return;
    }
    setCreatingUser(true);
    setError("");
    try {
      await apiCreateUser({
        tab_no: newUser.tab_no.trim(),
        fio: newUser.fio.trim(),
        role: newUser.role,
        site_code: newUser.site_code.trim() || null,
        site_name: newUser.site_name.trim() || null,
        status: newUser.status,
        password: newUser.password.trim(),
      });
      setInfo(`Пользователь создан: ${newUser.fio.trim()}`);
      setNewUser({
        tab_no: "",
        fio: "",
        role: settingsSub === "masters" ? "master" : "site_chief",
        site_code: "",
        site_name: "",
        status: "Активен",
        password: "",
      });
      setShowNewUser(false);
      await loadAllUsers();
      await reloadMasters();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось создать пользователя");
    } finally {
      setCreatingUser(false);
    }
  }

  async function uploadUsersFile(file: File) {
    setBusy(true);
    setError("");
    setInfo("");
    try {
      const res = await apiImportUpload({ base: null, users: file, carnet: null });
      setInfo(
        res
          .map((r) => `${r.source}: добавлено ${r.added}, обновлено ${r.updated}, пропущено ${r.skipped}`)
          .join(" · "),
      );
      await loadAllUsers();
      await reloadMasters();
      await loadDash();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Загрузка не удалась");
    } finally {
      setBusy(false);
      if (usersFileRef.current) usersFileRef.current.value = "";
    }
  }

  const userColumns = useMemo<ExcelColumn<AdminUser>[]>(
    () => [
      {
        id: "tab",
        title: "Таб. №",
        width: 120,
        minWidth: 90,
        sticky: "left",
        filter: "text",
        getValue: (u) => u.tab_no,
      },
      {
        id: "fio",
        title: "ФИО",
        width: 280,
        minWidth: 160,
        filter: "text",
        getValue: (u) => u.fio,
      },
      {
        id: "role",
        title: "Роль",
        width: 190,
        minWidth: 140,
        filter: "select",
        getValue: (u) => roleLabel(userDraft(u).role),
        render: (u) => (
          <select
            className="xls-input"
            value={userDraft(u).role}
            onChange={(e) => setUserDraft(u, { role: e.target.value })}
          >
            {ROLE_ORDER.map((r) => (
              <option key={r} value={r}>
                {roleLabel(r)}
              </option>
            ))}
          </select>
        ),
      },
      {
        id: "site_code",
        title: "Код участка",
        width: 140,
        minWidth: 100,
        filter: "text",
        getValue: (u) => userDraft(u).site_code,
        render: (u) => (
          <input
            className="xls-input"
            value={userDraft(u).site_code}
            placeholder="—"
            onChange={(e) => setUserDraft(u, { site_code: e.target.value })}
          />
        ),
      },
      {
        id: "site_name",
        title: "Участок",
        width: 260,
        minWidth: 150,
        filter: "text",
        getValue: (u) => userDraft(u).site_name,
        render: (u) => (
          <input
            className="xls-input"
            value={userDraft(u).site_name}
            placeholder="—"
            onChange={(e) => setUserDraft(u, { site_name: e.target.value })}
          />
        ),
      },
      {
        id: "status",
        title: "Статус",
        width: 130,
        minWidth: 100,
        filter: "select",
        getValue: (u) => userDraft(u).status,
        cellClassName: (u) =>
          userDraft(u).status === "Активен" ? "xls-cell-ok" : "xls-cell-no",
        render: (u) => (
          <select
            className="xls-input"
            value={userDraft(u).status}
            onChange={(e) => setUserDraft(u, { status: e.target.value })}
          >
            <option value="Активен">Активен</option>
            <option value="Отключен">Отключен</option>
          </select>
        ),
      },
      {
        id: "password",
        title: "Новый пароль",
        width: 150,
        minWidth: 110,
        filter: "none",
        getValue: () => "",
        render: (u) => (
          <input
            className="xls-input"
            type="password"
            autoComplete="new-password"
            value={userDraft(u).password}
            placeholder="не менять"
            onChange={(e) => setUserDraft(u, { password: e.target.value })}
          />
        ),
      },
      {
        id: "save",
        title: "",
        width: 110,
        minWidth: 90,
        filter: "none",
        align: "center",
        getValue: () => "",
        render: (u) => (
          <button
            type="button"
            className="primary xls-save-btn"
            disabled={savingUserId === u.id || !userDirty(u)}
            onClick={() => void saveUserRow(u)}
          >
            {savingUserId === u.id ? "…" : "Сохранить"}
          </button>
        ),
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [userEdits, savingUserId],
  );

  // ---------- Вторая оценка ----------
  const secondChief = useMemo(
    () => chiefs.find((c) => String(c.id) === secondChiefId) || null,
    [chiefs, secondChiefId],
  );

  const secondCounts = useMemo(() => {
    const out: Record<SecondGroup, number> = {
      all: 0,
      no_evaluators: 0,
      no_secondary: 0,
      on_first: 0,
      got_first: 0,
    };
    for (const g of SECOND_GROUPS) {
      out[g.id] = secondRows.filter(g.match).length;
    }
    return out;
  }, [secondRows]);

  /** Панель назначения 2-го оценщика активна в режиме «Назначить» и в группах «На 1 оценке» / «Получили 1 оценку» */
  const assignActive =
    assignMode || secondGroup === "on_first" || secondGroup === "got_first";

  const secondView = useMemo(() => {
    let list = secondRows;
    if (assignMode) {
      // Явный режим назначения: все, у кого есть 1-й оценщик
      list = list.filter((r) => !!r.primary_user_id);
    } else {
      const g = SECOND_GROUPS.find((x) => x.id === secondGroup);
      list = g ? list.filter(g.match) : list;
    }
    // При активном назначении и выбранном начальнике — только сотрудники его участка
    if (assignActive && secondChief) {
      if (!secondChief.site_name) return [];
      list = list.filter((r) => nfSite(r.site_name) === nfSite(secondChief.site_name));
    }
    return list;
  }, [secondRows, secondGroup, assignMode, assignActive, secondChief]);

  function toggleSecondSel(id: number) {
    setSecondSel((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  async function assignSecondaryBulk() {
    if (!secondChief || !secondSel.length) return;
    if (
      !window.confirm(
        `Назначить ${secondChief.fio} вторым оценщиком для отмеченных (${secondSel.length})?`,
      )
    )
      return;
    setBusy(true);
    setError("");
    try {
      const res = await apiAssignSecondary({
        assignment_ids: secondSel,
        secondary_user_id: secondChief.id,
      });
      const errTail = res.errors?.length ? ` · ошибки: ${res.errors.slice(0, 3).join("; ")}` : "";
      setInfo(`2-й оценщик ${secondChief.fio} назначен: ${res.updated} чел.${errTail}`);
      setSecondSel([]);
      await loadSecond();
      await loadDash();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось назначить 2-го оценщика");
    } finally {
      setBusy(false);
    }
  }

  async function removeSecondaryRow(assignmentId: number) {
    setBusy(true);
    setError("");
    try {
      await apiAssignSecondary({ assignment_ids: [assignmentId], secondary_user_id: null });
      setInfo("2-й оценщик снят");
      await loadSecond();
      await loadDash();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось снять 2-го оценщика");
    } finally {
      setBusy(false);
    }
  }

  const secondColumns = useMemo<ExcelColumn<SecondEvalRow>[]>(() => {
    const cols: ExcelColumn<SecondEvalRow>[] = [];
    if (assignActive) {
      cols.push({
        id: "sel",
        title: "☑",
        width: 44,
        minWidth: 40,
        sticky: "left",
        filter: "none",
        align: "center",
        getValue: () => "",
        render: (r) => {
          const hasSecondary = !!(r.dual_enabled && r.secondary_user_id);
          if (hasSecondary || !r.primary_user_id) return null;
          return (
            <input
              type="checkbox"
              checked={secondSel.includes(r.assignment_id)}
              onChange={() => toggleSecondSel(r.assignment_id)}
              aria-label={`Выбрать ${r.fio}`}
            />
          );
        },
      });
    }
    cols.push(
      {
        id: "tab",
        title: "Таб. №",
        width: 110,
        minWidth: 90,
        sticky: assignActive ? "left2" : "left",
        filter: "text",
        getValue: (r) => r.tab_no,
      },
      {
        id: "fio",
        title: "Сотрудник",
        width: 300,
        minWidth: 170,
        filter: "text",
        getValue: (r) => r.fio + (r.is_candidate ? " (кандидат)" : ""),
        render: (r) => (
          <>
            {r.fio}
            {r.is_candidate ? " (кандидат)" : ""}
            {r.site_name ? <div className="muted">{r.site_name}</div> : null}
          </>
        ),
      },
      {
        id: "site",
        title: "Участок",
        width: 200,
        minWidth: 120,
        filter: "select",
        getValue: (r) => r.site_name || "—",
      },
      {
        id: "primary",
        title: "1-й оценщик (мастер/ПР)",
        width: 240,
        minWidth: 150,
        filter: "text",
        getValue: (r) => r.primary_fio || "не назначен",
        render: (r) =>
          r.primary_fio ? (
            r.primary_fio
          ) : (
            <span className="xls-cell-empty">не назначен</span>
          ),
      },
      {
        id: "primary_status",
        title: "1-я оценка",
        width: 110,
        minWidth: 90,
        filter: "select",
        align: "center",
        getValue: (r) => (r.primary_user_id ? evalStatusLabel(r.primary_eval_status) : "—"),
        cellClassName: (r) =>
          !r.primary_user_id
            ? "xls-cell-no"
            : r.primary_eval_status === "submitted"
              ? "xls-cell-ok"
              : r.primary_eval_status === "draft"
                ? "xls-cell-warn"
                : "xls-cell-no",
      },
      {
        id: "secondary",
        title: "2-й оценщик (нач. участка)",
        width: 240,
        minWidth: 150,
        filter: "text",
        getValue: (r) => r.secondary_fio || "—",
        render: (r) =>
          r.dual_enabled && r.secondary_fio ? (
            r.secondary_fio
          ) : (
            <span className="xls-cell-empty">—</span>
          ),
      },
      {
        id: "secondary_status",
        title: "2-я оценка",
        width: 110,
        minWidth: 90,
        filter: "select",
        align: "center",
        getValue: (r) =>
          r.dual_enabled && r.secondary_user_id ? evalStatusLabel(r.secondary_eval_status) : "—",
        cellClassName: (r) =>
          !(r.dual_enabled && r.secondary_user_id)
            ? "xls-cell-no"
            : r.secondary_eval_status === "submitted"
              ? "xls-cell-ok"
              : r.secondary_eval_status === "draft"
                ? "xls-cell-warn"
                : "xls-cell-no",
      },
    );
    if (assignActive) {
      cols.push({
        id: "act",
        title: "Действие",
        width: 130,
        minWidth: 100,
        filter: "none",
        align: "center",
        getValue: () => "",
        render: (r) =>
          r.dual_enabled && r.secondary_user_id ? (
            <button
              type="button"
              className="xls-save-btn"
              disabled={busy}
              onClick={() => void removeSecondaryRow(r.assignment_id)}
            >
              Снять 2-го
            </button>
          ) : null,
      });
    }
    return cols;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assignActive, secondSel, busy]);

  const assignColumns = useMemo<ExcelColumn<AdminAssignment>[]>(
    () => [
      {
        id: "sel",
        title: "☑",
        width: 44,
        minWidth: 40,
        sticky: "left",
        filter: "none",
        align: "center",
        getValue: () => "",
        render: (a) => (
          <input
            type="checkbox"
            checked={selectedIds.includes(a.assignment_id)}
            onChange={() => toggleSelect(a.assignment_id)}
            aria-label={`Выбрать ${a.fio}`}
          />
        ),
      },
      {
        id: "tab",
        title: "Таб. №",
        width: 120,
        minWidth: 90,
        sticky: "left2",
        filter: "text",
        getValue: (a) => a.tab_no,
      },
      {
        id: "fio",
        title: "Сотрудник",
        width: 320,
        minWidth: 180,
        filter: "text",
        getValue: (a) => a.fio + (a.is_candidate ? " (кандидат)" : ""),
        render: (a) => (
          <>
            {a.fio}
            {a.is_candidate ? " (кандидат)" : ""}
            {a.site_name ? <div className="muted">{a.site_name}</div> : null}
          </>
        ),
      },
      {
        id: "evaluate",
        title: "На оценке",
        width: 100,
        minWidth: 80,
        filter: "select",
        align: "center",
        getValue: (a) => (a.evaluate ? "да" : "нет"),
        cellClassName: (a) => (a.evaluate ? "xls-cell-ok" : "xls-cell-no"),
        render: (a) => (a.evaluate ? "да" : "нет"),
      },
      {
        id: "primary",
        title: "Оценщик (прораб / мастер)",
        width: 280,
        minWidth: 160,
        filter: "text",
        getValue: (a) => (a.primary_fio ? `${a.primary_fio} ${a.primary_tab || ""}` : "не закреплён"),
        render: (a) =>
          a.primary_fio ? (
            <>
              <div>{a.primary_fio}</div>
              <div className="muted">{a.primary_tab}</div>
            </>
          ) : (
            <span className="xls-cell-empty">не закреплён</span>
          ),
      },
      {
        id: "role",
        title: "Роль",
        width: 100,
        minWidth: 80,
        filter: "select",
        getValue: (a) =>
          a.primary_role === "master" ? "мастер" : a.primary_role === "foreman" ? "прораб" : "—",
      },
    ],
    [selectedIds],
  );

  type UrgentRow = (typeof urgent)[number];

  const urgentColumns = useMemo<ExcelColumn<UrgentRow>[]>(() => {
    const cols: ExcelColumn<UrgentRow>[] = [
      {
        id: "id",
        title: "№",
        width: 70,
        minWidth: 50,
        filter: "text",
        getValue: (u) => String(u.id),
      },
      {
        id: "fio",
        title: "Сотрудник",
        width: 280,
        minWidth: 160,
        filter: "text",
        getValue: (u) => u.fio,
      },
      {
        id: "tab",
        title: "Таб. №",
        width: 120,
        minWidth: 90,
        filter: "text",
        getValue: (u) => u.tab_no,
      },
      {
        id: "evals",
        title: "Оценщики",
        width: 320,
        minWidth: 160,
        filter: "text",
        getValue: (u) => (u.evaluator_names || []).join(", ") || "—",
      },
      {
        id: "status",
        title: "Статус",
        width: 100,
        minWidth: 80,
        filter: "select",
        getValue: (u) => (u.status === "open" ? "открыта" : "закрыта"),
        cellClassName: (u) => (u.status === "open" ? "xls-cell-ok" : "xls-cell-no"),
      },
    ];
    if (!showClosedUrgent) {
      cols.push({
        id: "act",
        title: "Действие",
        width: 110,
        minWidth: 90,
        filter: "none",
        getValue: () => "",
        render: (u) => (
          <button type="button" disabled={busy} onClick={() => void closeUrgentRow(u.id)}>
            Закрыть
          </button>
        ),
      });
    }
    return cols;
  }, [busy, showClosedUrgent]);

  function go(tabId: Tab, opts?: { candidates?: boolean; mode?: typeof filterMode }) {
    if (opts?.candidates != null) setCandOnly(opts.candidates);
    if (opts?.mode) setFilterMode(opts.mode);
    setTab(tabId);
    setInfo("");
    setError("");
  }

  async function createUrgent() {
    setBusy(true);
    setError("");
    try {
      await apiCreateUrgent({
        employee_id: Number(urgEmpId),
        evaluator_user_ids: urgEvalIds,
        comment: urgComment.trim() || undefined,
      });
      setUrgEmpId("");
      setUrgEvalIds([]);
      setUrgEmpQ("");
      setUrgEvalQ("");
      setUrgComment("");
      setUrgent(await apiListUrgent());
      setInfo("Срочная оценка создана и отправлена оценщикам");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  async function closeUrgentRow(id: number) {
    setBusy(true);
    try {
      await apiCloseUrgent(id);
      setUrgent(await apiListUrgent());
      setInfo(`Заявка №${id} закрыта`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось закрыть");
    } finally {
      setBusy(false);
    }
  }

  async function runImportFolder() {
    setBusy(true);
    setInfo("");
    try {
      const res = await apiImportAll();
      setInfo(
        res
          .map((r) => `${r.source}: добавлено ${r.added}, обновлено ${r.updated}, пропущено ${r.skipped}`)
          .join(" · "),
      );
      await loadDash();
      await reloadMasters();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Импорт не удался");
    } finally {
      setBusy(false);
    }
  }

  async function runImportUpload() {
    setBusy(true);
    setInfo("");
    setError("");
    try {
      const res = await apiImportUpload({ base: fileBase, users: fileUsers, carnet: fileCarnet });
      setInfo(
        res
          .map((r) => `${r.source}: добавлено ${r.added}, обновлено ${r.updated}, пропущено ${r.skipped}`)
          .join(" · "),
      );
      setFileBase(null);
      setFileUsers(null);
      setFileCarnet(null);
      await loadDash();
      await reloadMasters();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Загрузка не удалась");
    } finally {
      setBusy(false);
    }
  }

  async function runBulk(opts: { primary?: boolean; evaluate?: boolean }) {
    const ids = selectedIds;
    if (!ids.length) {
      setError("Сначала отметьте галочками нужных сотрудников в таблице");
      return;
    }
    if (opts.primary && !selectedMasterId) {
      setError("Сначала выберите прораба/мастера в списке");
      return;
    }
    const actionLabel =
      opts.evaluate === true
        ? "отправить для оценки"
        : opts.evaluate === false
          ? "отозвать с оценки"
          : "закрепить за оценщиком";
    if (!window.confirm(`Выполнить «${actionLabel}» для выбранных (${ids.length})?`)) return;

    setBusy(true);
    setError("");
    try {
      const res = await apiBulkAssignments({
        assignment_ids: ids,
        primary_user_id: opts.primary ? Number(selectedMasterId) : undefined,
        evaluate: opts.evaluate,
      });
      const errTail = res.errors?.length ? ` · ошибки: ${res.errors.slice(0, 3).join("; ")}` : "";
      setInfo(
        opts.evaluate === true
          ? `Отправлено для оценки: ${res.updated}${errTail}`
          : opts.evaluate === false
            ? `Отозвано с оценки: ${res.updated}${errTail}`
            : `Закреплено за ${res.primary_fio || "оценщиком"}: ${res.updated}${errTail}`,
      );
      setSelectedIds([]);
      setAssignments(await apiAdminAssignments({}));
      await loadDash();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Массовая операция не удалась");
    } finally {
      setBusy(false);
    }
  }

  function toggleSelect(id: number) {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  function toggleSelectAllFiltered() {
    const ids = (visibleAssignRows.length ? visibleAssignRows : filteredAssignments).map(
      (a) => a.assignment_id,
    );
    const allOn = ids.length > 0 && ids.every((id) => selectedIds.includes(id));
    setSelectedIds(allOn ? selectedIds.filter((id) => !ids.includes(id)) : [...new Set([...selectedIds, ...ids])]);
  }

  function masterName(id: number) {
    return masters.find((m) => m.id === id)?.fio || `№${id}`;
  }

  return (
    <div className="page excel-page admin-glass">
      <div className="admin-bg" aria-hidden>
        {BG_IMAGES.map((src, i) => (
          <img
            key={src}
            className={`admin-bg-photo ${i === bgIndex ? "is-active" : ""}`}
            src={src}
            alt=""
          />
        ))}
        <div className="admin-bg-shade" />
      </div>
      <div className="admin-foreground">
        <div className="admin-accent-bar" aria-hidden />
        <div className="admin-topbar">
          <div className="admin-brandline">
            ОМиК / ВелесстройМонтаж / ОП Кингисепп 2. ЕвроХим — Система оценки персонала
          </div>
          <div className="admin-topbar-actions">
            <button type="button" className="pill" onClick={onOpenRegistry}>
              Реестр
            </button>
            <button type="button" className="pill ghost" onClick={onLogout}>
              Выйти
            </button>
          </div>
        </div>

      <nav className="tabs" aria-label="Разделы">
        {TABS.map((t) => (
          <div key={t.id} className="tab-tip-wrap">
            <button
              type="button"
              className={tab === t.id ? "tab active" : "tab"}
              onClick={() => setTab(t.id)}
              aria-describedby={`tip-${t.id}`}
            >
              {t.label}
            </button>
            <div className="tab-tip" id={`tip-${t.id}`} role="tooltip">
              <strong>{t.tipTitle}</strong>
              <span>{t.tip}</span>
            </div>
          </div>
        ))}
      </nav>

      {error && <p className="error">{error}</p>}
      {info && <p className="ok-text">{info}</p>}

      {tab === "dash" && dash && (
        <>
          <section className="hero-card">
            <p className="muted">Период оценки · ВелесстройМонтаж · Кингисепп</p>
            <h1>{dash.period_code}</h1>
            <p className="muted">{dash.organization}</p>
            <div className="progress-block">
              <div className="progress-meta">
                <span>
                  Сдано анкет: {dash.submitted_evaluations} из {dash.evaluate_yes}
                </span>
                <strong>{progress}%</strong>
              </div>
              <div className="progress-bar" aria-hidden>
                <span style={{ width: `${Math.min(progress, 100)}%` }} />
              </div>
            </div>
          </section>

          <div className="help-box">
            <strong>Как оценивают с телефона?</strong>
            <span className="muted">
              Мастер или прораб входит своим табельным — видит свой список и ставит оценки. Здесь отдел
              мобилизации назначает, кто кого оценивает, и загружает Excel.
            </span>
          </div>

          <section className="dash-grid">
              <DashCard
                cls="info"
                icon="📋"
                label="В реестре закреплений"
                value={dash.total_assignments}
                hint="открыть таблицу назначений"
                tipTitle="Реестр закреплений"
                tip="Полный реестр всех закреплений сотрудников за оценщиками. Клик — открыть таблицу назначений."
                onClick={() => go("assign", { mode: "all" })}
              />
              <DashCard
                cls="ok"
                icon="✅"
                label="Идут на оценку"
                value={dash.evaluate_yes}
                hint="только отмеченные к оценке"
                tipTitle="Идут на оценку"
                tip="Сотрудники, отмеченные к оценке в текущем периоде. Клик — фильтр «на оценке»."
                onClick={() => go("assign", { mode: "evaluate" })}
              />
              <DashCard
                cls=""
                icon="👤"
                label="Есть основной оценщик"
                value={dash.with_primary}
                hint="с назначенным мастером/ПР"
                tipTitle="Есть основной оценщик"
                tip="Закрепления, у которых назначен основной оценщик (мастер/ПР)."
                onClick={() => go("assign", { mode: "with_primary" })}
              />
              <DashCard
                cls={dash.awaiting_primary ? "warn" : ""}
                icon="⏳"
                label="Ждут назначения"
                value={dash.awaiting_primary}
                hint="без оценщика — назначить"
                tipTitle="Ждут назначения"
                tip="Сотрудники без оценщика — нужно назначить. Клик — список ожидания."
                onClick={() => go("assign", { mode: "awaiting" })}
              />
              <DashCard
                cls={dash.candidates ? "info" : ""}
                icon="🆕"
                label="Кандидаты"
                value={dash.candidates}
                hint="открыть базу кандидатов"
                tipTitle="Кандидаты"
                tip="Новые кандидаты в базе. Клик — открыть базу кандидатов."
                onClick={() => go("employees", { candidates: true })}
              />
              <DashCard
                cls=""
                icon="👥"
                label="Двойная оценка"
                value={dash.dual_enabled}
                hint="два независимых оценщика"
                tipTitle="Двойная оценка"
                tip="Закрепления с двумя независимыми оценщиками — для исключения путаницы и коррупции."
                onClick={() => go("assign", { mode: "dual" })}
              />
              <DashCard
                cls={dash.open_urgent ? "warn" : "ok"}
                icon="⚡"
                label="Срочные оценки"
                value={dash.open_urgent}
                hint="открытые срочные запросы"
                tipTitle="Срочные оценки"
                tip="Открытые срочные запросы с площадки. Клик — вкладка «Срочная»."
                onClick={() => go("urgent")}
              />
              <DashCard
                cls={dash.open_tickets ? "warn" : "ok"}
                icon="💬"
                label="Обращения с площадки"
                value={dash.open_tickets}
                hint="ошибки в списках"
                tipTitle="Обращения с площадки"
                tip="Обращения об ошибках в списках. Клик — вкладка «Обращения»."
                onClick={() => go("tickets")}
              />
              <DashCard
                cls={dash.escalations ? "danger" : "ok"}
                icon="🚨"
                label="Эскалации"
                value={dash.escalations}
                hint="нет входа > 3 дней"
                tipTitle="Эскалации"
                tip="Сотрудники без захода в кабинет более 3 дней при незакрытых оценках. Клик — блок эскалаций."
                onClick={() => document.getElementById("escalations-block")?.scrollIntoView({ behavior: "smooth" })}
              />
              <DashCard
                cls="ok"
                icon="📊"
                label="Сдано анкет"
                value={dash.submitted_evaluations}
                hint="открыть реестр итогов"
                tipTitle="Сдано анкет"
                tip="Завершённые и сданные оценки. Клик — реестр итогов."
                onClick={() => onOpenRegistry()}
              />
          </section>

          <section className="panel" id="escalations-block">
            <h2>Кто не заходит в систему</h2>
            <p className="muted">Нет входа больше 3 дней при незакрытых оценках.</p>
            {escalations.length === 0 && <p className="ok-text">Сейчас эскалаций нет.</p>}
            <div className="excel-wrap">
              <table className="excel-table">
                <thead>
                  <tr>
                    <th>ФИО</th>
                    <th>Таб. №</th>
                    <th>Осталось</th>
                    <th>Сдано</th>
                    <th>Всего</th>
                  </tr>
                </thead>
                <tbody>
                  {escalations.map((e) => (
                    <tr key={e.user_id}>
                      <td>{e.fio}</td>
                      <td>{e.tab_no}</td>
                      <td>{Math.max(e.pending_assignments - e.submitted, 0)}</td>
                      <td>{e.submitted}</td>
                      <td>{e.pending_assignments}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      {tab === "assign" && (
        <section className="panel excel-panel">
            <h2>Закрепление: сотрудник → прораб / мастер</h2>
            <p className="muted" style={{ marginTop: 0 }}>
              В реестре {assignStats.total} человек: с оценщиком {assignStats.withPrimary}, без оценщика{" "}
              {assignStats.awaiting}.
            </p>

            <div className="assign-view-tabs">
              <button
                type="button"
                className={filterMode === "with_primary" ? "active" : ""}
                onClick={() => setFilterMode("with_primary")}
              >
                С оценщиком · {assignStats.withPrimary}
              </button>
              <button
                type="button"
                className={filterMode === "awaiting" ? "active" : ""}
                onClick={() => setFilterMode("awaiting")}
              >
                Без оценщика · {assignStats.awaiting}
              </button>
              <button
                type="button"
                className={filterMode === "evaluate" ? "active" : ""}
                onClick={() => setFilterMode("evaluate")}
              >
                На оценке · {assignStats.onEval}
              </button>
              <button
                type="button"
                className={filterMode === "dual" ? "active" : ""}
                onClick={() => setFilterMode("dual")}
              >
                Двойная · {assignStats.dual}
              </button>
              <button
                type="button"
                className={filterMode === "all" ? "active" : ""}
                onClick={() => setFilterMode("all")}
              >
                Весь реестр · {assignStats.total}
              </button>
            </div>

            <div className="bulk-bar panel assign-control-bar">
              <label className="toolbar-select assign-master-select">
                Прораб / мастер
                <select
                  value={selectedMasterId}
                  onChange={(e) => {
                    const id = e.target.value;
                    setSelectedMasterId(id);
                    if (id && filterMode === "awaiting") {
                      /* оставляем «Без оценщика» — назначаем им выбранного */
                    } else if (id) {
                      setFilterMode("with_primary");
                    }
                  }}
                >
                  <option value="">— все оценщики —</option>
                  {masters.map((m) => {
                    const n = masterCounts.find((c) => c.userId === m.id)?.n ?? 0;
                    return (
                      <option key={m.id} value={m.id}>
                        {m.fio} · {m.role === "master" ? "мастер" : "прораб"}
                        {n ? ` · ${n} чел.` : ""}
                      </option>
                    );
                  })}
                </select>
              </label>
            <input
                className="assign-search"
                placeholder="Поиск: ФИО или табельный"
              value={assignQ}
              onChange={(e) => setAssignQ(e.target.value)}
            />
            <button
              type="button"
                onClick={async () => {
                  setAssignments(await apiAdminAssignments({}));
                  setSelectedIds([]);
                }}
            >
                Обновить
            </button>
              <span className="muted">
                На экране: <strong>{filteredAssignments.length}</strong>
                {selectedIds.length ? ` · отмечено ${selectedIds.length}` : ""}
              </span>
            </div>

            <div className="bulk-bar panel">
              <p className="muted" style={{ margin: 0, flex: "1 1 100%" }}>
                {selectedMaster ? (
                  <>
                    Выбран: <strong>{selectedMaster.fio}</strong>. Отметьте людей галочками, затем назначьте им этого
                    оценщика. После назначения нажмите «Отправить на оценку» — список появится у него в кабинете.
                  </>
                ) : (
                  <>Сначала выберите прораба/мастера в списке выше. Затем отметьте сотрудников и назначьте их ему.</>
                )}
              </p>
              <button
                type="button"
                className="primary"
                disabled={busy || !selectedIds.length || !selectedMasterId}
                onClick={() => runBulk({ primary: true })}
                title="Прописать выбранным сотрудникам этого прораба/мастера как основного оценщика"
              >
                Назначить отмеченных → {selectedMaster ? selectedMaster.fio.split(" ").slice(0, 2).join(" ") : "…"}
              </button>
              <button
                type="button"
                className="primary"
                disabled={busy || !selectedIds.length}
                onClick={() => runBulk({ evaluate: true })}
                title="Показать отмеченных в личном кабинете оценщика для заполнения анкеты"
              >
                Отправить на оценку
              </button>
              <button
                type="button"
                disabled={busy || !selectedIds.length}
                onClick={() => runBulk({ evaluate: false })}
                title="Убрать отмеченных из списка оценки у прораба/мастера (закрепление остаётся)"
              >
                Снять с оценки
              </button>
              <button type="button" className="ghost" disabled={busy} onClick={toggleSelectAllFiltered}>
                Отметить всех на экране
              </button>
              <button type="button" className="ghost" disabled={!selectedIds.length} onClick={() => setSelectedIds([])}>
                Снять отметки
              </button>
            </div>

            <div className="assign-select-all-bar">
            <label className="check">
              <input
                type="checkbox"
                  checked={
                    (visibleAssignRows.length ? visibleAssignRows : filteredAssignments).length > 0 &&
                    (visibleAssignRows.length ? visibleAssignRows : filteredAssignments).every((a) =>
                      selectedIds.includes(a.assignment_id),
                    )
                  }
                  onChange={toggleSelectAllFiltered}
              />
                Отметить всех на экране (с учётом фильтров колонок)
              </label>
          </div>

            <ExcelSheet
              rows={filteredAssignments}
              columns={assignColumns}
              rowKey={(a) => a.assignment_id}
              rowClassName={(a) => (!a.primary_user_id ? "xls-warn" : undefined)}
              onVisibleRowsChange={setVisibleAssignRows}
              emptyText={
                selectedMasterId && filterMode !== "awaiting"
                  ? "У этого оценщика пока никого нет. Откройте «Без оценщика», отметьте людей и нажмите «Назначить»."
                  : "Нет строк. Смените вкладку сверху или сбросьте поиск / фильтры в заголовках."
              }
            />
          </section>
        )}

        {tab === "second" && (
          <section className="panel excel-panel">
            <h2>Вторая оценка</h2>
            <p className="muted" style={{ marginTop: 0 }}>
              Второй независимый оценщик — <strong>начальник участка</strong>. Назначить можно только на сотрудников
              его участка (совпадение по полю «Участок») и только тем, у кого уже есть 1-й оценщик.
            </p>

            <div className="assign-view-tabs">
              {SECOND_GROUPS.map((g) => (
                <button
                  key={g.id}
                  type="button"
                  className={!assignMode && secondGroup === g.id ? "active" : ""}
                  onClick={() => {
                    setSecondGroup(g.id);
                    setAssignMode(false);
                    setSecondSel([]);
                  }}
                >
                {g.label} · {secondCounts[g.id]}
              </button>
            ))}
              <button
                type="button"
                className={assignMode ? "active" : ""}
                onClick={() => {
                  setAssignMode(true);
                  setSecondSel([]);
                }}
              >
                Назначить 2 оценщика
              </button>
            </div>

            {assignActive && (
              <div className="bulk-bar panel assign-control-bar">
                <label className="toolbar-select assign-master-select">
                  Начальник участка
                  <select
                    value={secondChiefId}
                    onChange={(e) => {
                      setSecondChiefId(e.target.value);
                      setSecondSel([]);
                    }}
                  >
                    <option value="">— выберите начальника участка —</option>
                    {chiefs.map((c) => {
                      const match = secondRows.filter(
                        (r) =>
                          r.primary_user_id &&
                          !(r.dual_enabled && r.secondary_user_id) &&
                          c.site_name &&
                          nfSite(r.site_name) === nfSite(c.site_name),
                      ).length;
                      return (
                        <option key={c.id} value={c.id}>
                          {c.fio} · {c.site_name || "участок не указан"}
                          {match ? ` · доступно ${match} чел.` : ""}
                        </option>
                    );
                  })}
                  </select>
                </label>
                <button
                  type="button"
                  className="primary"
                  disabled={busy || !secondChief || !secondSel.length}
                  onClick={() => void assignSecondaryBulk()}
                  title="Назначить выбранного начальника участка 2-м оценщиком отмеченным сотрудникам"
                >
                  Назначить 2-го →{" "}
                  {secondChief ? secondChief.fio.split(" ").slice(0, 2).join(" ") : "…"}
                </button>
                <button
                  type="button"
                  onClick={async () => {
                    await loadSecond();
                    setSecondSel([]);
                  }}
                >
                  Обновить
                </button>
                <span className="muted">
                  На экране: <strong>{secondView.length}</strong>
                  {secondSel.length ? ` · отмечено ${secondSel.length}` : ""}
                </span>
              </div>
            )}
            {assignActive && secondChief && (
              <p className="muted" style={{ margin: "0 0 0.6rem" }}>
                Показаны сотрудники участка <strong>{secondChief.site_name}</strong>
                {assignMode ? " с 1-м оценщиком" : " из этой группы"}. Отметьте галочками, кому назначить 2-го.
                Кнопка «Снять 2-го» убирает текущего 2-го оценщика.
              </p>
            )}
            {assignActive && !secondChief && (
              <p className="muted" style={{ margin: "0 0 0.6rem" }}>
                Выберите начальника участка — список сократится до сотрудников его участка.
              </p>
            )}

            <ExcelSheet
              rows={secondView}
              columns={secondColumns}
              rowKey={(r) => r.assignment_id}
              rowClassName={(r) =>
                assignActive &&
                  secondChief &&
                  r.primary_user_id &&
                  !(r.dual_enabled && r.secondary_user_id)
                  ? undefined
                  : assignActive
                    ? "xls-row-dim"
                    : !r.primary_user_id
                      ? "xls-warn"
                      : undefined
              }
              emptyText={
                assignActive
                  ? secondChief
                    ? "На участке этого начальника нет подходящих сотрудников."
                    : "Выберите начальника участка выше."
                  : "Нет строк в этой группе. Переключите группу сверху."
              }
            />
        </section>
      )}

      {tab === "urgent" && (
          <section className="panel urgent-panel">
            <div className="urgent-head">
              <div className="urgent-head-line">
                <h2>Срочная оценка</h2>
                <span className="muted">
                  внеплановая анкета: сотрудник + оценщики · одна открытая заявка на человека
                </span>
              </div>
              <div className="urgent-stats">
                <span className="pill warn">Открыто · {openUrgent.length}</span>
                <span className="pill">В архиве · {closedUrgent.length}</span>
              </div>
            </div>

            <div className="urgent-create">
              <div className="urgent-step">
                <div className="urgent-step-num">1</div>
                <div className="urgent-step-body">
                  <strong>Кого оценить</strong>
                <input
                    placeholder="Поиск: ФИО или табельный номер"
                  value={urgEmpQ}
                    onChange={(e) => {
                      setUrgEmpQ(e.target.value);
                      setUrgEmpId("");
                    }}
                />
                  {selectedUrgEmp ? (
                    <div className="urgent-selected">
                      <div>
                        <strong>{selectedUrgEmp.fio}</strong>
                        <div className="muted">{selectedUrgEmp.tab_no}</div>
                      </div>
                      <button
                        type="button"
                        className="ghost"
                        onClick={() => {
                          setUrgEmpId("");
                        setUrgEmpQ("");
                        }}
                      >
                        Сменить
                      </button>
                    </div>
                  ) : (
                    urgEmpQ.trim().length >= 2 && (
                      <div className="urgent-suggest">
                        {urgEmpCandidates.length === 0 ? (
                          <p className="muted">Никого не найдено</p>
                        ) : (
                          urgEmpCandidates.map((e) => {
                            const hasOpen = openUrgent.some((u) => u.employee_id === e.id);
                            return (
                              <button
                                key={e.id}
                                type="button"
                                className={`urgent-suggest-item ${hasOpen ? "blocked" : ""}`}
                                disabled={hasOpen}
                                onClick={() => {
                                  setUrgEmpId(String(e.id));
                                  setUrgEmpQ(e.fio);
                                }}
                              >
                                <span>
                                  <strong>{e.fio}</strong>
                                  <span className="muted"> · {e.tab_no}</span>
                                </span>
                                {hasOpen && <span className="pill danger">уже открыта</span>}
                              </button>
                            );
                          })
                        )}
                        </div>
                      )
                )}
                </div>
              </div>

              <div className="urgent-step">
                <div className="urgent-step-num">2</div>
                <div className="urgent-step-body">
                  <strong>Кто оценивает</strong>
                  <input
                    placeholder="Поиск мастера / прораба"
                    value={urgEvalQ}
                    onChange={(e) => setUrgEvalQ(e.target.value)}
                  />
                  <div className="urgent-chips">
                    {urgMasterCandidates.map((m) => {
                      const on = urgEvalIds.includes(m.id);
                      return (
                        <button
                        key={m.id}
                        type="button"
                        className={`urgent-chip ${on ? "on" : ""}`}
                        onClick={() =>
                          setUrgEvalIds((prev) =>
                            on ? prev.filter((id) => id !== m.id) : [...prev, m.id],
                          )
                        }
                      >
                        {m.fio.split(" ").slice(0, 2).join(" ")}
                        <span className="muted">
                          {" "}
                          · {m.role === "master" ? "мастер" : "прораб"}
                        </span>
                      </button>
                    );
                  })}
                  </div>
                  {urgEvalIds.length > 0 && (
                    <p className="muted" style={{ margin: "0.35rem 0 0" }}>
                      Выбрано:{" "}
                      {masters
                        .filter((m) => urgEvalIds.includes(m.id))
                        .map((m) => m.fio.split(" ").slice(0, 2).join(" "))
                        .join(", ")}
                    </p>
                  )}
                </div>
              </div>

              <div className="urgent-step">
                <div className="urgent-step-num">3</div>
                <div className="urgent-step-body">
                  <strong>Комментарий (необязательно)</strong>
                  <input
                    placeholder="Например: увольнение / перевод / запрос руководства"
                    value={urgComment}
                    onChange={(e) => setUrgComment(e.target.value)}
                  />
                  <button
                    type="button"
                    className="primary urgent-create-btn"
                    disabled={busy || !urgEmpId || urgEvalIds.length === 0}
                    onClick={() => void createUrgent()}
                  >
                    Создать срочную оценку
                  </button>
                </div>
              </div>
            </div>

            <div className="urgent-table-block">
              <div className="urgent-table-tabs">
                <button
                  type="button"
                  className={!showClosedUrgent ? "active" : ""}
                  onClick={() => setShowClosedUrgent(false)}
                >
                  Открытые · {openUrgent.length}
                </button>
                <button
                  type="button"
                  className={showClosedUrgent ? "active" : ""}
                  onClick={() => setShowClosedUrgent(true)}
                >
                  Архив · {closedUrgent.length}
                </button>
              </div>

              <ExcelSheet
                rows={showClosedUrgent ? closedUrgent : openUrgent}
                columns={urgentColumns}
                rowKey={(u) => u.id}
                emptyText={
                  showClosedUrgent ? "Архив пуст — закрытых заявок нет" : "Нет открытых срочных заявок"
                }
              />
          </div>
        </section>
      )}

      {tab === "delegate" && (
        <section className="panel">
          <h2>Замещение</h2>
          <div className="row">
            <select value={delOrig} onChange={(e) => setDelOrig(e.target.value)}>
              <option value="">Кого замещаем…</option>
              {masters.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.fio}
                </option>
              ))}
            </select>
            <select value={delSub} onChange={(e) => setDelSub(e.target.value)}>
              <option value="">Кто замещает…</option>
              {masters.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.fio}
                </option>
              ))}
            </select>
            <input type="date" value={delFrom} onChange={(e) => setDelFrom(e.target.value)} />
            <input type="date" value={delTo} onChange={(e) => setDelTo(e.target.value)} />
            <button
              type="button"
              className="primary"
                disabled={busy || !delOrig || !delSub || !delFrom || !delTo || delOrig === delSub}
              onClick={async () => {
                setBusy(true);
                try {
                  await apiCreateDelegation({
                    original_user_id: Number(delOrig),
                    substitute_user_id: Number(delSub),
                    starts_on: delFrom,
                    ends_on: delTo,
                  });
                  setDelegations(await apiDelegations());
                  setInfo("Замещение создано");
                } catch (e) {
                  setError(e instanceof Error ? e.message : "Ошибка");
                } finally {
                  setBusy(false);
                }
              }}
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
                    <td>{masterName(d.original_user_id)}</td>
                    <td>{masterName(d.substitute_user_id)}</td>
                    <td>{d.starts_on}</td>
                    <td>{d.ends_on}</td>
                    <td>{d.is_active ? "действует" : "снято"}</td>
                    <td>
                      {d.is_active && (
                        <button
                          type="button"
                          onClick={async () => {
                            await apiDeactivateDelegation(d.id);
                            setDelegations(await apiDelegations());
                          }}
                        >
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
      )}

      {tab === "employees" && (
        <section className="panel excel-panel">
          <h2>База сотрудников</h2>
          <div className="excel-toolbar">
            <input
              placeholder="Фильтр ФИО / таб.№"
              value={empQ}
              onChange={(e) => setEmpQ(e.target.value)}
            />
            <button
              type="button"
              onClick={async () =>
                setEmployees(await apiEmployees({ q: empQ || undefined, candidates: candOnly }))
              }
            >
              Применить
            </button>
            <label className="check">
              <input type="checkbox" checked={candOnly} onChange={(e) => setCandOnly(e.target.checked)} />
              только кандидаты
            </label>
          </div>
          <div className="row">
            <input placeholder="Табельный №" value={newTab} onChange={(e) => setNewTab(e.target.value)} />
            <input placeholder="ФИО" value={newFio} onChange={(e) => setNewFio(e.target.value)} />
            <button
              type="button"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await apiCreateEmployee({ tab_no: newTab, fio: newFio, is_candidate: false });
                  setNewTab("");
                  setNewFio("");
                  setEmployees(await apiEmployees({ q: empQ || undefined, candidates: candOnly }));
                  setInfo("Сотрудник добавлен");
                } catch (e) {
                  setError(e instanceof Error ? e.message : "Ошибка");
                } finally {
                  setBusy(false);
                }
              }}
            >
              Добавить в базу
            </button>
          </div>
          <div className="row">
            <select value={formalizeId} onChange={(e) => setFormalizeId(e.target.value)}>
              <option value="">Оформить кандидата…</option>
              {employees
                .filter((e) => e.is_candidate)
                .map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.fio} ({e.tab_no})
                  </option>
                ))}
            </select>
            <input
              placeholder="Новый табельный №"
              value={formalizeTab}
              onChange={(e) => setFormalizeTab(e.target.value)}
            />
            <button
              type="button"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await apiFormalizeCandidate({
                    employee_id: Number(formalizeId),
                    new_tab_no: formalizeTab,
                  });
                  setFormalizeId("");
                  setFormalizeTab("");
                  setEmployees(await apiEmployees({ candidates: true }));
                  setInfo("Кандидат оформлен");
                } catch (e) {
                  setError(e instanceof Error ? e.message : "Ошибка");
                } finally {
                  setBusy(false);
                }
              }}
            >
              Оформить
            </button>
          </div>
          <div className="excel-wrap tall">
            <table className="excel-table sticky">
              <thead>
                <tr>
                  <th>id</th>
                  <th>Таб. №</th>
                  <th>ФИО</th>
                  <th>Должность</th>
                  <th>Кандидат</th>
                  <th>Дата приёма</th>
                </tr>
              </thead>
              <tbody>
                {employees.map((e) => (
                  <tr key={e.id} className={e.is_candidate ? "row-info" : undefined}>
                    <td>{e.id}</td>
                    <td>{e.tab_no}</td>
                    <td>{e.fio}</td>
                    <td>{e.position_1c || "—"}</td>
                    <td>{e.is_candidate ? "да" : "нет"}</td>
                    <td>{e.hire_date || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {tab === "tickets" && (
        <section className="panel form-panel">
          <h2>Обращения с площадки</h2>
          <p className="muted">Видно, кто написал. Можно ответить мастеру — он увидит ответ в своём списке обращений.</p>
          <div className="ticket-list">
            {tickets.length === 0 && <p className="muted">Обращений пока нет</p>}
            {tickets.map((t) => (
              <article key={t.id} className="ticket-card">
                <div className="ticket-card-head">
                  <strong>№{t.id}</strong>
                  <span className={`pill ${t.status === "done" ? "ok" : t.status === "new" ? "warn" : "info"}`}>
                    {t.status === "done" ? "закрыто" : t.status === "new" ? "новое" : "в работе"}
                  </span>
                  <span className="muted">{t.created_at}</span>
                </div>
                <p>
                  <strong>От кого:</strong> {t.created_by_fio || "—"}{" "}
                  <span className="muted">({t.created_by_tab_no || t.created_by_user_id})</span>
                </p>
                <p>
                  <strong>Сообщение:</strong> {t.message}
                </p>
                {t.admin_note && (
                  <p className="ok-text">
                    <strong>Ваш ответ:</strong> {t.admin_note}
                  </p>
                )}
                <label>
                  Ответ мастеру
                  <textarea
                    rows={2}
                    placeholder="Напишите ответ…"
                    value={replyDrafts[t.id] ?? t.admin_note ?? ""}
                    onChange={(e) => setReplyDrafts((d) => ({ ...d, [t.id]: e.target.value }))}
                  />
                </label>
                <div className="row">
                  <button
                    type="button"
                    className="primary"
                    disabled={busy}
                    onClick={async () => {
                      setBusy(true);
                      try {
                        const note = (replyDrafts[t.id] ?? "").trim();
                        await apiPatchTicket(t.id, {
                          admin_note: note || undefined,
                          status: note ? "in_progress" : undefined,
                        });
                        setTickets(await apiTickets());
                        setInfo(`Ответ по обращению №${t.id} сохранён`);
                      } catch (e) {
                        setError(e instanceof Error ? e.message : "Ошибка");
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    Отправить ответ
                  </button>
                  {t.status !== "done" && (
                    <button
                      type="button"
                      onClick={async () => {
                        await apiPatchTicket(t.id, {
                          status: "done",
                          admin_note: (replyDrafts[t.id] ?? t.admin_note ?? "закрыто").trim(),
                        });
                        setTickets(await apiTickets());
                      }}
                    >
                      Закрыть обращение
                    </button>
                  )}
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      {tab === "events" && (
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
      )}

        {tab === "settings" && (
          <section className="panel excel-panel">
            <h2>Настройки</h2>

            <div className="assign-view-tabs">
              <button
                type="button"
                className={settingsSub === "import" ? "active" : ""}
                onClick={() => setSettingsSub("import")}
              >
                Импорт Excel
              </button>
              <button
                type="button"
                className={settingsSub === "masters" ? "active" : ""}
                onClick={() => setSettingsSub("masters")}
              >
                Прораб / Мастер · {settingsCounts.masters}
              </button>
              <button
                type="button"
                className={settingsSub === "chiefs" ? "active" : ""}
                onClick={() => setSettingsSub("chiefs")}
              >
                Начальник участка и др. · {settingsCounts.chiefs}
              </button>
            </div>

            {settingsSub === "import" && (
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
                      onChange={(e) => setFileBase(e.target.files?.[0] || null)}
                    />
                    {fileBase && <span className="ok-text">{fileBase.name}</span>}
                  </label>
                  <label className="upload-card">
                    <strong>2. Пользователи</strong>
                    <span className="muted">файл 02_Пользователи.xlsx</span>
                    <input
                      type="file"
                      accept=".xlsx,.xls"
                      onChange={(e) => setFileUsers(e.target.files?.[0] || null)}
                    />
                    {fileUsers && <span className="ok-text">{fileUsers.name}</span>}
                  </label>
                  <label className="upload-card">
                    <strong>3. Реестр закрепления</strong>
                    <span className="muted">файл 03_Реестр_закрепления.xlsx</span>
                    <input
                      type="file"
                      accept=".xlsx,.xls"
                      onChange={(e) => setFileCarnet(e.target.files?.[0] || null)}
                    />
                    {fileCarnet && <span className="ok-text">{fileCarnet.name}</span>}
                  </label>
                </div>

                <div className="row" style={{ marginTop: "1rem" }}>
                  <button
                    type="button"
                    className="primary"
                    disabled={busy || (!fileBase && !fileUsers && !fileCarnet)}
                    onClick={runImportUpload}
                  >
                    {busy ? "Загрузка…" : "Загрузить выбранные файлы"}
                  </button>
                  <button type="button" disabled={busy} onClick={runImportFolder}>
                    Импорт из папки Files на сервере
                  </button>
                </div>
                <p className="muted" style={{ marginTop: "0.75rem" }}>
                  После загрузки данные сразу попадают в назначения, базу и пользователей. Можно повторять импорт —
                  строки обновятся.
                </p>
              </>
            )}

            {settingsSub !== "import" && (
              <>
                <p className="muted" style={{ marginTop: 0 }}>
                  {settingsSub === "masters"
                    ? "Пользователи с ролью «Мастер» или «Производитель работ» из файла 02_Пользователи.xlsx."
                    : "Начальники участков и остальные пользователи из файла 02_Пользователи.xlsx."}{" "}
                  Правьте роль, участок, статус или пароль и нажимайте «Сохранить» в строке. Пустое поле пароля — не
                  менять.
                </p>
                <div className="excel-toolbar">
                  <input
                    placeholder="Поиск: ФИО / таб.№ / участок"
                    value={userQ}
                    onChange={(e) => setUserQ(e.target.value)}
                  />
                  <button
                    type="button"
                    className="primary"
                    onClick={() => {
                      setShowNewUser((v) => !v);
                      setNewUser((p) => ({
                        ...p,
                        role: settingsSub === "masters" ? "master" : "site_chief",
                      }));
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
                      if (f) void uploadUsersFile(f);
                    }}
                  />
                  <button type="button" onClick={() => void loadAllUsers()}>
                    Обновить
                  </button>
                  <span className="muted">
                    На экране: <strong>{settingsUsers.length}</strong>
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
                      onChange={(e) => setNewUser({ ...newUser, tab_no: e.target.value })}
                      style={{ width: 130 }}
                    />
                    <input
                      placeholder="ФИО *"
                      value={newUser.fio}
                      onChange={(e) => setNewUser({ ...newUser, fio: e.target.value })}
                      style={{ minWidth: 220 }}
                    />
                    <select
                      value={newUser.role}
                      onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
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
                      onChange={(e) => setNewUser({ ...newUser, site_code: e.target.value })}
                      style={{ width: 110 }}
                    />
                    <input
                      placeholder="Участок"
                      value={newUser.site_name}
                      onChange={(e) => setNewUser({ ...newUser, site_name: e.target.value })}
                      style={{ width: 170 }}
                    />
                    <select
                      value={newUser.status}
                      onChange={(e) => setNewUser({ ...newUser, status: e.target.value })}
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
                      onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                      style={{ width: 120 }}
                    />
                    <button type="button" className="primary" disabled={creatingUser} onClick={() => void createUser()}>
                      {creatingUser ? "Создаю…" : "Создать"}
                    </button>
                  </div>
                )}
                <ExcelSheet
                  rows={settingsUsers}
                  columns={userColumns}
                  rowKey={(u) => u.id}
                  defaultRowHeight={36}
                  emptyText="Нет пользователей в этой группе."
                />
              </>
            )}
        </section>
      )}
      </div>
    </div>
  );
}
