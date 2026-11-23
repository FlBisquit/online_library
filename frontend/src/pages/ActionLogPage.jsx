import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../api/client";
import { Loading } from "../components/Loading";
import { EmptyState } from "../components/EmptyState";
import { ErrorMessage } from "../components/ErrorMessage";

const ACTION_LABELS = {
  "issue.create": "Выдача книги",
  "issue.return": "Возврат книги",
  "issue.mark_lost": "Отметка об утере",
  "issue.status_change": "Изменение статуса выдачи",
  "queue.join": "Вступление в очередь",
  "reservation.cancel": "Отмена бронирования",
  "reservation.expire": "Истечение бронирования",
  "reservation.status_change": "Изменение статуса бронирования",
  "bookcopy.status_change": "Изменение статуса экземпляра",
};

const STATUS_LABELS = {
  ISSUED: "Выдано",
  RETURNED: "Возвращено",
  OVERDUE: "Просрочено",
  LOST: "Потеряно",
  PENDING: "В очереди",
  ACTIVE: "Активно",
  FULFILLED: "Выполнено",
  CANCELLED: "Отменено",
  EXPIRED: "Истекло",
  AVAILABLE: "Доступно",
  RESERVED: "Зарезервировано",
  RETIRED: "Списано",
};

const ENTITY_LABELS = {
  Issue: "Выдача",
  Reservation: "Бронирование",
  BookCopy: "Экземпляр",
  Reader: "Читатель",
  Book: "Книга",
};

const EMPTY_FILTERS = {
  user: "",
  entity_type: "",
  entity_id: "",
  action: "",
  date_from: "",
  date_to: "",
};

const label = (labels, value) => (value ? labels[value] ?? value : "—");

const formatDate = (value) => {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString("ru-RU");
};

export const ActionLogPage = ({ readOnly = false }) => {
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [applied, setApplied] = useState(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [data, setData] = useState({ results: [], count: 0, next: null, previous: null });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get("/action-log/", {
        params: { ...applied, page },
      });
      setData(response);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [applied, page]);

  useEffect(() => {
    load();
  }, [load]);

  const setFilter = (key, value) => {
    setFilters((previous) => ({ ...previous, [key]: value }));
  };

  const handleApply = (event) => {
    event.preventDefault();
    setPage(1);
    setApplied(filters);
  };

  const handleReset = () => {
    setFilters(EMPTY_FILTERS);
    setPage(1);
    setApplied(EMPTY_FILTERS);
  };

  const totalPages = Math.max(1, Math.ceil((data.count ?? 0) / 20));

  return (
    <section>
      <h3>
        Журнал действий {readOnly && <span className="badge">Только для чтения</span>}
      </h3>
      <form className="filter-row log-filters" onSubmit={handleApply}>
        <input
          className="input"
          type="number"
          min="1"
          placeholder="ID пользователя"
          value={filters.user}
          onChange={(event) => setFilter("user", event.target.value)}
        />
        <select
          className="input"
          value={filters.entity_type}
          onChange={(event) => setFilter("entity_type", event.target.value)}
        >
          <option value="">Все объекты</option>
          <option value="Issue">Выдача</option>
          <option value="Reservation">Бронирование</option>
          <option value="BookCopy">Экземпляр</option>
        </select>
        <input
          className="input"
          type="number"
          min="1"
          placeholder="ID объекта"
          value={filters.entity_id}
          onChange={(event) => setFilter("entity_id", event.target.value)}
        />
        <select
          className="input"
          value={filters.action}
          onChange={(event) => setFilter("action", event.target.value)}
        >
          <option value="">Все действия</option>
          {Object.entries(ACTION_LABELS).map(([value, text]) => (
            <option key={value} value={value}>
              {text}
            </option>
          ))}
        </select>
        <input
          className="input"
          type="date"
          aria-label="Дата с"
          value={filters.date_from}
          onChange={(event) => setFilter("date_from", event.target.value)}
        />
        <input
          className="input"
          type="date"
          aria-label="Дата по"
          value={filters.date_to}
          onChange={(event) => setFilter("date_to", event.target.value)}
        />
        <button className="btn" type="submit">
          Применить
        </button>
        <button className="btn btn-secondary" type="button" onClick={handleReset}>
          Сбросить
        </button>
      </form>

      <ErrorMessage message={error} />
      {loading && <Loading message="Загрузка журнала..." />}
      {!loading && !error && data.results.length === 0 && (
        <EmptyState message="Записи журнала не найдены." />
      )}
      {!loading && !error && data.results.length > 0 && (
        <div className="table-wrap">
          <table className="log-table">
            <thead>
              <tr>
                <th>Дата и время</th>
                <th>Кто</th>
                <th>Действие</th>
                <th>Объект</th>
                <th>Было</th>
                <th>Стало</th>
                <th>Подробности</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((row) => (
                <tr key={row.id}>
                  <td>{formatDate(row.created_at)}</td>
                  <td>
                    {row.user
                      ? `${row.user.full_name} (${row.user.email})`
                      : "Система"}
                  </td>
                  <td>{label(ACTION_LABELS, row.action)}</td>
                  <td>
                    {label(ENTITY_LABELS, row.entity_type)}
                    {row.entity_id ? ` #${row.entity_id}` : ""}
                  </td>
                  <td>{label(STATUS_LABELS, row.old_status)}</td>
                  <td>{label(STATUS_LABELS, row.new_status)}</td>
                  <td>{row.details && Object.keys(row.details).length ? JSON.stringify(row.details) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && !error && data.count > 0 && (
        <div className="pagination">
          <button
            className="btn btn-secondary"
            disabled={!data.previous}
            onClick={() => setPage((current) => Math.max(1, current - 1))}
          >
            ← Назад
          </button>
          <span>
            Страница {page} из {totalPages} (записей: {data.count})
          </span>
          <button
            className="btn btn-secondary"
            disabled={!data.next}
            onClick={() => setPage((current) => current + 1)}
          >
            Вперёд →
          </button>
        </div>
      )}
    </section>
  );
};
