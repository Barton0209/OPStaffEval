import { useEffect, useState } from "react";

// ==================== Types ====================

interface Territory {
  id: number;
  code: string;
  name: string;
}

interface Department {
  id: number;
  name: string;
}

interface GroupOfUser {
  id: number;
  territory_id: number | null;
  territory_name: string | null;
  department_id: number | null;
  department_name: string | null;
  group_name: string | null;
  permission: string | null;
}

interface GroupUser {
  id: number;
  tab_no: string;
  fio: string;
  role: string;
  status: string;
}

interface PhotoItem {
  name: string;
  url: string;
  path: string;
}

// ==================== API Helpers ====================

async function fetchJson(url: string, options?: RequestInit): Promise<any> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.json();
}

// ==================== Component ====================

export function GroupsPanel() {
  const [territories, setTerritories] = useState<Territory[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [groups, setGroups] = useState<GroupOfUser[]>([]);
  const [groupUsers, setGroupUsers] = useState<GroupUser[]>([]);
  const [photos, setPhotos] = useState<PhotoItem[]>([]);
  const [selectedTerritory, setSelectedTerritory] = useState<string>("");
  const [selectedDepartment, setSelectedDepartment] = useState<string>("");
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);

  // Form state
  const [formTerritory, setFormTerritory] = useState("");
  const [formDepartment, setFormDepartment] = useState("");
  const [formGroupName, setFormGroupName] = useState("");
  const [formPermission, setFormPermission] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);

  // Photo state
  const [showPhotos, setShowPhotos] = useState(false);

  // Load data
  useEffect(() => {
    loadTerritories();
    loadGroups();
    loadPhotos();
  }, []);

  useEffect(() => {
    if (selectedTerritory) {
      loadDepartments(selectedTerritory);
    }
  }, [selectedTerritory]);

  useEffect(() => {
    loadGroups();
  }, [selectedTerritory, selectedDepartment]);

  useEffect(() => {
    if (selectedGroupId) {
      loadGroupUsers(selectedGroupId);
    }
  }, [selectedGroupId]);

  async function loadTerritories() {
    try {
      const data = await fetchJson("/api/groups/territories");
      setTerritories(data);
    } catch (e) {
      console.error("Failed to load territories:", e);
    }
  }

  async function loadDepartments(territory: string) {
    try {
      const data = await fetchJson(`/api/groups/departments?territory=${encodeURIComponent(territory)}`);
      setDepartments(data);
    } catch (e) {
      console.error("Failed to load departments:", e);
    }
  }

  async function loadGroups() {
    try {
      const params = new URLSearchParams();
      if (selectedTerritory) params.set("territory", selectedTerritory);
      if (selectedDepartment) params.set("department", selectedDepartment);
      const query = params.toString();
      const data = await fetchJson(`/api/groups${query ? "?" + query : ""}`);
      setGroups(data);
    } catch (e) {
      console.error("Failed to load groups:", e);
    }
  }

  async function loadGroupUsers(groupId: number) {
    try {
      const data = await fetchJson(`/api/groups/${groupId}/users`);
      setGroupUsers(data);
    } catch (e) {
      console.error("Failed to load group users:", e);
    }
  }

  async function loadPhotos() {
    try {
      const data = await fetchJson("/api/groups/photos");
      setPhotos(data.photos || []);
    } catch (e) {
      console.error("Failed to load photos:", e);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!formGroupName.trim()) return;

    setLoading(true);
    try {
      if (editingId) {
        await fetchJson(`/api/groups/${editingId}`, {
          method: "PUT",
          body: JSON.stringify({
            territory_name: formTerritory,
            department_name: formDepartment || null,
            group_name: formGroupName,
            permission: formPermission || null,
          }),
        });
      } else {
        await fetchJson("/api/groups", {
          method: "POST",
          body: JSON.stringify({
            territory_name: formTerritory,
            department_name: formDepartment || null,
            group_name: formGroupName,
            permission: formPermission || null,
          }),
        });
      }
      resetForm();
      loadGroups();
    } catch (e) {
      console.error("Failed to save group:", e);
      alert("Ошибка при сохранении группы");
    } finally {
      setLoading(false);
    }
  }

  function resetForm() {
    setFormTerritory("");
    setFormDepartment("");
    setFormGroupName("");
    setFormPermission("");
    setEditingId(null);
  }

  function handleEdit(group: GroupOfUser) {
    setEditingId(group.id);
    setFormTerritory(group.territory_name || "");
    setFormDepartment(group.department_name || "");
    setFormGroupName(group.group_name || "");
    setFormPermission(group.permission || "");
  }

  async function handleDelete(groupId: number) {
    if (!confirm("Удалить группу?")) return;
    try {
      await fetchJson(`/api/groups/${groupId}`, { method: "DELETE" });
      loadGroups();
      if (selectedGroupId === groupId) {
        setSelectedGroupId(null);
        setGroupUsers([]);
      }
    } catch (e) {
      console.error("Failed to delete group:", e);
      alert("Ошибка при удалении группы");
    }
  }

  return (
    <div className="settings-panel">
      <h2>Управление группами пользователей</h2>

      {/* Фильтры */}
      <div className="form-row" style={{ marginBottom: 16 }}>
        <div className="form-group">
          <label>Площадка</label>
          <select
            value={selectedTerritory}
            onChange={(e) => setSelectedTerritory(e.target.value)}
          >
            <option value="">Все площадки</option>
            {territories.map((t) => (
              <option key={t.id} value={t.name}>
                {t.name}
              </option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label>Отдел</label>
          <select
            value={selectedDepartment}
            onChange={(e) => setSelectedDepartment(e.target.value)}
          >
            <option value="">Все отделы</option>
            {departments.map((d) => (
              <option key={d.id} value={d.name}>
                {d.name}
              </option>
            ))}
          </select>
        </div>

        <button
          type="button"
          className="secondary"
          onClick={() => {
            setSelectedTerritory("");
            setSelectedDepartment("");
          }}
        >
          Сбросить
        </button>
      </div>

      {/* Форма добавления/редактирования */}
      <form onSubmit={handleSubmit} className="form-card">
        <h3>{editingId ? "Редактировать группу" : "Новая группа"}</h3>

        <div className="form-row">
          <div className="form-group">
            <label>Площадка *</label>
            <select
              value={formTerritory}
              onChange={(e) => setFormTerritory(e.target.value)}
              required
            >
              <option value="">Выберите площадку</option>
              {territories.map((t) => (
                <option key={t.id} value={t.name}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Отдел</label>
            <input
              type="text"
              value={formDepartment}
              onChange={(e) => setFormDepartment(e.target.value)}
              placeholder="Например: ЦОК_Адаптация"
            />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>Название группы *</label>
            <input
              type="text"
              value={formGroupName}
              onChange={(e) => setFormGroupName(e.target.value)}
              placeholder="Например: Прорабы"
              required
            />
          </div>

          <div className="form-group">
            <label>Разрешение</label>
            <input
              type="text"
              value={formPermission}
              onChange={(e) => setFormPermission(e.target.value)}
              placeholder="Например: read_write"
            />
          </div>
        </div>

        <div className="form-actions">
          <button type="submit" className="primary" disabled={loading}>
            {editingId ? "Сохранить" : "Создать"}
          </button>
          {editingId && (
            <button type="button" className="secondary" onClick={resetForm}>
              Отмена
            </button>
          )}
        </div>
      </form>

      {/* Список групп */}
      <div className="form-card" style={{ marginTop: 16 }}>
        <h3>Группы ({groups.length})</h3>
        {groups.length === 0 ? (
          <p style={{ color: "#888" }}>Нет групп. Создайте первую.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Площадка</th>
                <th>Отдел</th>
                <th>Группа</th>
                <th>Разрешение</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {groups.map((g) => (
                <tr
                  key={g.id}
                  style={{
                    backgroundColor: selectedGroupId === g.id ? "#e3f2fd" : undefined,
                    cursor: "pointer",
                  }}
                  onClick={() => setSelectedGroupId(g.id)}
                >
                  <td>{g.territory_name || "-"}</td>
                  <td>{g.department_name || "-"}</td>
                  <td>
                    <strong>{g.group_name}</strong>
                  </td>
                  <td>{g.permission || "-"}</td>
                  <td>
                    <button
                      type="button"
                      className="icon"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleEdit(g);
                      }}
                      title="Редактировать"
                    >
                      ✏️
                    </button>
                    <button
                      type="button"
                      className="icon danger"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(g.id);
                      }}
                      title="Удалить"
                    >
                      🗑️
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Пользователи в группе */}
      {selectedGroupId && (
        <div className="form-card" style={{ marginTop: 16 }}>
          <h3>Пользователи в группе</h3>
          <p style={{ color: "#666" }}>
            Выберите группу из списка выше для просмотра пользователей
          </p>
          {groupUsers.length === 0 ? (
            <p style={{ color: "#888" }}>В группе нет пользователей</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Табельный №</th>
                  <th>ФИО</th>
                  <th>Роль</th>
                  <th>Статус</th>
                </tr>
              </thead>
              <tbody>
                {groupUsers.map((u) => (
                  <tr key={u.id}>
                    <td>{u.tab_no}</td>
                    <td>{u.fio}</td>
                    <td>{u.role}</td>
                    <td>{u.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Фото */}
      <div className="form-card" style={{ marginTop: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3>Фото для фонов и заставок</h3>
          <button
            type="button"
            className="secondary"
            onClick={() => setShowPhotos(!showPhotos)}
          >
            {showPhotos ? "Скрыть" : "Показать"} ({photos.length})
          </button>
        </div>

        {showPhotos && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 12, marginTop: 12 }}>
            {photos.length === 0 ? (
              <p style={{ color: "#888" }}>Нет фото в директории @Files/UpLoad/Foto</p>
            ) : (
              photos.map((p) => (
                <div
                  key={p.name}
                  style={{
                    border: "1px solid #ddd",
                    borderRadius: 8,
                    overflow: "hidden",
                    textAlign: "center",
                  }}
                >
                  <img
                    src={p.url}
                    alt={p.name}
                    style={{
                      width: "100%",
                      height: 120,
                      objectFit: "cover",
                    }}
                  />
                  <div style={{ padding: "8px 4px", fontSize: 12, color: "#666" }}>
                    {p.name}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}
