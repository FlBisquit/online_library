import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../api/client";
import { Loading } from "../components/Loading";
import { EmptyState } from "../components/EmptyState";
import { ErrorMessage } from "../components/ErrorMessage";
import { Pagination } from "../components/Pagination";
import { extractFieldErrors, extractGeneralError } from "../utils/formErrors";

const EMPTY_FORM = {
  email: "",
  password: "",
  full_name: "",
  phone: "",
  role: "librarian",
};

const FieldError = ({ errors, name }) =>
  errors[name] ? <div className="field-error">{errors[name]}</div> : null;

export const UsersAdminPage = () => {
  const [users, setUsers] = useState({ results: [], count: 0, next: null, previous: null });
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [applied, setApplied] = useState({ search: "", role: "", status: "" });
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingUser, setEditingUser] = useState(null);
  const [editForm, setEditForm] = useState({ role: "reader", status: "ACTIVE" });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.get("/users/", {
        params: {
          search: applied.search || undefined,
          role: applied.role || undefined,
          status: applied.status || undefined,
          page,
          limit: 20,
        },
      });
      setUsers(data);
    } catch (e) {
      setError(extractGeneralError(e));
    } finally {
      setLoading(false);
    }
  }, [applied, page]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const handleApply = (event) => {
    event.preventDefault();
    setPage(1);
    setApplied({ search, role: roleFilter, status: statusFilter });
  };

  const handleReset = () => {
    setSearch("");
    setRoleFilter("");
    setStatusFilter("");
    setPage(1);
    setApplied({ search: "", role: "", status: "" });
  };

  const handleCreate = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setErrors({});
    try {
      await apiClient.post("/users/", {
        email: form.email,
        password: form.password,
        full_name: form.full_name,
        phone: form.phone || undefined,
        role: form.role,
      });
      setForm(EMPTY_FORM);
      await loadUsers();
    } catch (e) {
      setErrors(extractFieldErrors(e));
      setError(extractGeneralError(e));
    } finally {
      setBusy(false);
    }
  };

  const startEdit = (user) => {
    setEditingUser(user);
    setEditForm({ role: user.role ?? "reader", status: user.status });
    setErrors({});
  };

  const handleUpdate = async (event) => {
    event.preventDefault();
    if (!editingUser) return;
    setBusy(true);
    setError(null);
    setErrors({});
    try {
      await apiClient.patch(`/users/${editingUser.id}/`, editForm);
      setEditingUser(null);
      await loadUsers();
    } catch (e) {
      setErrors(extractFieldErrors(e));
      setError(extractGeneralError(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <section>
        <h3>{editingUser ? `Изменение пользователя ${editingUser.email}` : "Создание сотрудника"}</h3>
        {editingUser ? (
          <form className="admin-form" onSubmit={handleUpdate}>
            <label className="multi-label">
              Роль
              <select className="input" value={editForm.role} onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}>
                <option value="reader">Читатель</option>
                <option value="librarian">Библиотекарь</option>
                <option value="admin">Администратор</option>
              </select>
            </label>
            <FieldError errors={errors} name="role" />
            <label className="multi-label">
              Статус
              <select className="input" value={editForm.status} onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}>
                <option value="ACTIVE">Активен</option>
                <option value="BLOCKED">Заблокирован</option>
              </select>
            </label>
            <FieldError errors={errors} name="status" />
            <div className="admin-actions">
              <button className="btn" type="submit" disabled={busy}>Сохранить</button>
              <button className="btn btn-secondary" type="button" onClick={() => setEditingUser(null)}>Отмена</button>
            </div>
          </form>
        ) : (
          <form className="admin-form" onSubmit={handleCreate}>
            <input className="input" placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
            <FieldError errors={errors} name="email" />
            <input className="input" placeholder="Пароль" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
            <FieldError errors={errors} name="password" />
            <input className="input" placeholder="ФИО" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required />
            <FieldError errors={errors} name="full_name" />
            <input className="input" placeholder="Телефон" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            <label className="multi-label">
              Роль
              <select className="input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                <option value="librarian">Библиотекарь</option>
                <option value="admin">Администратор</option>
              </select>
            </label>
            <FieldError errors={errors} name="role" />
            <button className="btn" type="submit" disabled={busy}>Создать пользователя</button>
          </form>
        )}
      </section>

      <section>
        <h3>Пользователи</h3>
        <form className="filter-row log-filters" onSubmit={handleApply}>
          <input className="input" placeholder="Email или ФИО" value={search} onChange={(e) => setSearch(e.target.value)} />
          <select className="input" value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
            <option value="">Все роли</option>
            <option value="reader">Читатель</option>
            <option value="librarian">Библиотекарь</option>
            <option value="admin">Администратор</option>
          </select>
          <select className="input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">Все статусы</option>
            <option value="ACTIVE">Активен</option>
            <option value="BLOCKED">Заблокирован</option>
          </select>
          <button className="btn" type="submit">Применить</button>
          <button className="btn btn-secondary" type="button" onClick={handleReset}>Сбросить</button>
        </form>
        <ErrorMessage message={error} />
        {loading && <Loading message="Загрузка пользователей..." />}
        {!loading && users.results.length === 0 && <EmptyState message="Пользователи не найдены." />}
        {!loading && users.results.length > 0 && (
          <div className="table-wrap">
            <table className="log-table">
              <thead>
                <tr>
                  <th>Email</th>
                  <th>ФИО</th>
                  <th>Роль</th>
                  <th>Статус</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {users.results.map((user) => (
                  <tr key={user.id}>
                    <td>{user.email}</td>
                    <td>{user.full_name}</td>
                    <td>{user.role}</td>
                    <td>{user.status}</td>
                    <td>
                      <button className="btn btn-secondary" type="button" onClick={() => startEdit(user)}>Изменить</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pagination
          page={page}
          count={users.count}
          pageSize={20}
          hasPrevious={Boolean(users.previous)}
          hasNext={Boolean(users.next)}
          disabled={loading}
          onPrevious={() => setPage((current) => Math.max(1, current - 1))}
          onNext={() => setPage((current) => current + 1)}
        />
      </section>
    </div>
  );
};
