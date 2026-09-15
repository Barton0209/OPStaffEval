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
  apiImportDailyAssignees,
  apiImportTariffGrid,
  apiImportUpload,
  apiListUrgent,
  apiPatchEmployee,
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

import type { ExcelColumn } from "./ExcelSheet";
import { NotificationBell } from "./NotificationBell";
import { AssignmentsPanel } from "./admin/AssignmentsPanel";
import { DashboardPanel } from "./admin/DashboardPanel";
import { DelegationsPanel } from "./admin/DelegationsPanel";
import { EmployeesPanel } from "./admin/EmployeesPanel";
import { EventsPanel } from "./admin/EventsPanel";
import { GroupsPanel } from "./admin/GroupsPanel";
import { SecondEvalPanel } from "./admin/SecondEvalPanel";
import { SettingsPanel } from "./admin/SettingsPanel";
import { TicketsPanel } from "./admin/TicketsPanel";
import { UrgentPanel } from "./admin/UrgentPanel";
import {
  BG_IMAGES,
  ROLE_LABELS,
  ROLE_ORDER,
  SECOND_GROUPS,
  TABS,
  evalStatusLabel,
  nfSite,
  pct,
  roleLabel,
  type DelegationRow,
  type EscalationRow,
  type EventRow,
  type FilterMode,
  type NewUserDraft,
  type SecondGroup,
  type SettingsSub,
  type Tab,
  type UrgentItem,
  type UserDraft,
} from "./admin/common";

type Props = {
  user: SessionUser;
  onLogout: () => void;
  onOpenRegistry: () => void;
};

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

  const [urgent, setUrgent] = useState<UrgentItem[]>([]);
  const [urgEmpId, setUrgEmpId] = useState("");
  const [urgEmpQ, setUrgEmpQ] = useState("");
  const [urgEvalIds, setUrgEvalIds] = useState<number[]>([]);
  const [urgEvalQ, setUrgEvalQ] = useState("");
  const [showClosedUrgent, setShowClosedUrgent] = useState(false);
  const [urgComment, setUrgComment] = useState("");
  const [replyDrafts, setReplyDrafts] = useState<Record<number, string>>({});

  const [delegations, setDelegations] = useState<DelegationRow[]>([]);
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
  const [events, setEvents] = useState<EventRow[]>([]);
  const [escalations, setEscalations] = useState<EscalationRow[]>([]);

  const [filterMode, setFilterMode] = useState<FilterMode>("with_primary");
  const [visibleAssignRows, setVisibleAssignRows] = useState<AdminAssignment[]>([]);
  const [fileBase, setFileBase] = useState<File | null>(null);
  const [fileUsers, setFileUsers] = useState<File | null>(null);
  const [fileCarnet, setFileCarnet] = useState<File | null>(null);
  const [fileUd, setFileUd] = useState<File | null>(null);
  const [fileDaily, setFileDaily] = useState<File | null>(null);

  // Настройки: пользователи (роли/участки/статусы/пароли)
  const [settingsSub, setSettingsSub] = useState<SettingsSub>("import");
  const [allUsers, setAllUsers] = useState<AdminUser[]>([]);
  const [userEdits, setUserEdits] = useState<Record<number, UserDraft>>({});
  const [savingUserId, setSavingUserId] = useState<number | null>(null);
  const [userQ, setUserQ] = useState("");
  const [showNewUser, setShowNewUser] = useState(false);
  const [creatingUser, setCreatingUser] = useState(false);
  const [newUser, setNewUser] = useState<NewUserDraft>({
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

  const urgentColumns = useMemo<ExcelColumn<UrgentItem>[]>(() => {
    const cols: ExcelColumn<UrgentItem>[] = [
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

  function go(tabId: Tab, opts?: { candidates?: boolean; mode?: FilterMode }) {
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
      const res = await apiImportUpload({
        base: fileBase,
        users: fileUsers,
        carnet: fileCarnet,
        ud: fileUd,
      });
      setInfo(
        res
          .map((r) => `${r.source}: добавлено ${r.added}, обновлено ${r.updated}, пропущено ${r.skipped}`)
          .join(" · "),
      );
      setFileBase(null);
      setFileUsers(null);
      setFileCarnet(null);
      setFileUd(null);
      await loadDash();
      await reloadMasters();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Загрузка не удалась");
    } finally {
      setBusy(false);
    }
  }

  async function uploadTariffGrid(file: File) {
    setBusy(true);
    setError("");
    setInfo("");
    try {
      const res = await apiImportTariffGrid(file);
      setInfo(
        res
          .map((r) => `${r.source}: добавлено ${r.added}, обновлено ${r.updated}, пропущено ${r.skipped}`)
          .join(" · "),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Загрузка тарифной сетки не удалась");
    } finally {
      setBusy(false);
    }
  }

  async function runUploadDaily(file: File) {
    setBusy(true);
    setError("");
    setInfo("");
    try {
      const res = await apiImportDailyAssignees(file);
      const errors = res.errors?.length
        ? ` · ошибок: ${res.errors.length}${res.errors.slice(0, 3).map((e) => `; ${e}`).join("")}`
        : "";
      setInfo(`Ежедневная выгрузка: добавлено ${res.added}, обновлено ${res.updated}, пропущено ${res.skipped}${errors}`);
      setFileDaily(null);
      await Promise.all([loadDash(), reloadMasters(), reloadAssignments()]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Импорт ежедневной выгрузки не удался");
    } finally {
      setBusy(false);
    }
  }

  async function patchEmpRate(emp: AdminEmployee, newRate: number) {
    setBusy(true);
    setError("");
    try {
      const updated = await apiPatchEmployee(emp.id, { hourly_rate: newRate });
      setEmployees((prev) => prev.map((e) => (e.id === updated.id ? updated : e)));
      setInfo(
        `ЧТС сохранено: ${updated.fio} — ${updated.hourly_rate} (поднятие ${updated.rate_last_raised || "—"})`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось сохранить ЧТС");
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

  // ---------- Функции-обработчики панелей ----------
  async function reloadAssignments() {
    setAssignments(await apiAdminAssignments({}));
    setSelectedIds([]);
  }

  async function createDelegation() {
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
  }

  async function deactivateDelegation(id: number) {
    await apiDeactivateDelegation(id);
    setDelegations(await apiDelegations());
  }

  async function applyEmpFilter() {
    setEmployees(await apiEmployees({ q: empQ || undefined, candidates: candOnly }));
  }

  async function addEmployee() {
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
  }

  async function formalizeCandidateAction() {
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
  }

  async function sendTicketReply(t: Ticket) {
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
  }

  async function closeTicket(t: Ticket) {
    await apiPatchTicket(t.id, {
      status: "done",
      admin_note: (replyDrafts[t.id] ?? t.admin_note ?? "закрыто").trim(),
    });
    setTickets(await apiTickets());
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
            <NotificationBell variant="topbar" />
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
          <DashboardPanel
            dash={dash}
            progress={progress}
            escalations={escalations}
            onGo={go}
            onOpenRegistry={onOpenRegistry}
          />
        )}

        {tab === "assign" && (
          <AssignmentsPanel
            assignments={assignments}
            filteredAssignments={filteredAssignments}
            visibleAssignRows={visibleAssignRows}
            onVisibleRowsChange={setVisibleAssignRows}
            assignStats={assignStats}
            assignQ={assignQ}
            onAssignQ={setAssignQ}
            selectedMasterId={selectedMasterId}
            onSelectedMasterId={setSelectedMasterId}
            masters={masters}
            masterCounts={masterCounts}
            selectedMaster={selectedMaster}
            filterMode={filterMode}
            onFilterMode={setFilterMode}
            columns={assignColumns}
            busy={busy}
            selectedIds={selectedIds}
            onSelectedIds={setSelectedIds}
            onBulk={(opts) => void runBulk(opts)}
            onToggleSelectAll={toggleSelectAllFiltered}
            onReload={reloadAssignments}
          />
        )}

        {tab === "second" && (
          <SecondEvalPanel
            rows={secondView}
            columns={secondColumns}
            counts={secondCounts}
            group={secondGroup}
            onGroup={(g) => {
              setSecondGroup(g);
              setAssignMode(false);
              setSecondSel([]);
            }}
            assignMode={assignMode}
            onAssignMode={(v) => {
              setAssignMode(v);
              setSecondSel([]);
            }}
            assignActive={assignActive}
            chiefs={chiefs}
            chiefId={secondChiefId}
            onChiefId={(v) => {
              setSecondChiefId(v);
              setSecondSel([]);
            }}
            chief={secondChief}
            busy={busy}
            selected={secondSel}
            onAssignBulk={() => void assignSecondaryBulk()}
            onReload={async () => {
              await loadSecond();
              setSecondSel([]);
            }}
          />
        )}

        {tab === "urgent" && (
          <UrgentPanel
            openUrgent={openUrgent}
            closedUrgent={closedUrgent}
            showClosed={showClosedUrgent}
            onShowClosed={setShowClosedUrgent}
            columns={urgentColumns}
            employees={employees}
            empQ={urgEmpQ}
            onEmpQ={setUrgEmpQ}
            empId={urgEmpId}
            onEmpId={setUrgEmpId}
            empCandidates={urgEmpCandidates}
            selectedEmp={selectedUrgEmp}
            masters={masters}
            evalQ={urgEvalQ}
            onEvalQ={setUrgEvalQ}
            evalIds={urgEvalIds}
            onEvalIds={setUrgEvalIds}
            masterCandidates={urgMasterCandidates}
            comment={urgComment}
            onComment={setUrgComment}
            busy={busy}
            onCreate={() => void createUrgent()}
          />
        )}

        {tab === "delegate" && (
          <DelegationsPanel
            masters={masters}
            delegations={delegations}
            orig={delOrig}
            onOrig={setDelOrig}
            sub={delSub}
            onSub={setDelSub}
            from={delFrom}
            onFrom={setDelFrom}
            to={delTo}
            onTo={setDelTo}
            busy={busy}
            onMasterName={masterName}
            onCreate={() => void createDelegation()}
            onDeactivate={(id) => void deactivateDelegation(id)}
          />
        )}

        {tab === "employees" && (
          <EmployeesPanel
            employees={employees}
            empQ={empQ}
            onEmpQ={setEmpQ}
            candOnly={candOnly}
            onCandOnly={setCandOnly}
            newTab={newTab}
            onNewTab={setNewTab}
            newFio={newFio}
            onNewFio={setNewFio}
            formalizeId={formalizeId}
            onFormalizeId={setFormalizeId}
            formalizeTab={formalizeTab}
            onFormalizeTab={setFormalizeTab}
            busy={busy}
            onApply={() => void applyEmpFilter()}
            onAdd={() => void addEmployee()}
            onFormalize={() => void formalizeCandidateAction()}
            onPatchRate={(emp, r) => patchEmpRate(emp, r)}
          />
        )}

        {tab === "tickets" && (
          <TicketsPanel
            tickets={tickets}
            replyDrafts={replyDrafts}
            onReplyDraft={(id, v) => setReplyDrafts((d) => ({ ...d, [id]: v }))}
            busy={busy}
            onSendReply={(t) => void sendTicketReply(t)}
            onCloseTicket={(t) => void closeTicket(t)}
          />
        )}

        {tab === "events" && <EventsPanel events={events} />}

        {tab === "groups" && <GroupsPanel />}

        {tab === "settings" && (
          <SettingsPanel
            sub={settingsSub}
            onSub={setSettingsSub}
            counts={settingsCounts}
            fileBase={fileBase}
            onFileBase={setFileBase}
            fileUsers={fileUsers}
            onFileUsers={setFileUsers}
            fileCarnet={fileCarnet}
            onFileCarnet={setFileCarnet}
            fileUd={fileUd}
            onFileUd={setFileUd}
            busy={busy}
            onUpload={() => void runImportUpload()}
            onImportFolder={() => void runImportFolder()}
            onUploadTariffGrid={(f) => void uploadTariffGrid(f)}
            fileDaily={fileDaily}
            onFileDaily={setFileDaily}
            onUploadDaily={(f) => void runUploadDaily(f)}
            users={settingsUsers}
            userQ={userQ}
            onUserQ={setUserQ}
            userEdits={userEdits}
            savingUserId={savingUserId}
            columns={userColumns}
            showNewUser={showNewUser}
            onToggleNewUser={() => setShowNewUser((v) => !v)}
            newUser={newUser}
            onNewUser={setNewUser}
            creatingUser={creatingUser}
            onCreateUser={() => void createUser()}
            usersFileRef={usersFileRef}
            onUploadUsersFile={(f) => void uploadUsersFile(f)}
            onReloadUsers={async () => {
              await loadAllUsers();
            }}
          />
        )}
      </div>
    </div>
  );
}