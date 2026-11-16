import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export const LibrarianPage = () => {
  const { user } = useAuth();
  const [issues, setIssues] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [returningId, setReturningId] = useState(null);

  const loadIssues = useCallback(async (statusValue) => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.get("/issues/", {
        params: { status: statusValue || undefined, limit: 50 },
      });
      setIssues(data.results ?? []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadIssues(statusFilter);
  }, [loadIssues, statusFilter]);

  const handleReturn = async (issueId) => {
    setReturningId(issueId);
    setError(null);
    try {
      await apiClient.post(`/issues/${issueId}/return/`, {});
      await loadIssues(statusFilter);
    } catch (e) {
      setError(e.message);
    } finally {
      setReturningId(null);
    }
  };

  return (
    <div className="page">
      <h2>Панель библиотекаря</h2>
      <div className="filter-row">
        <select className="input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">Все статусы</option>
          <option value="ISSUED">Выдано</option>
          <option value="RETURNED">Возвращено</option>
          <option value="OVERDUE">Просрочено</option>
          <option value="LOST">Потеряно</option>
        </select>
      </div>
      {loading && <div className="loading">Загрузка выдач...</div>}
      {error && <div className="alert alert-error">{error}</div>}
      {!loading && !error && issues.length === 0 && <div className="empty">Выдачи не найдены.</div>}
      <div className="book-list">
        {issues.map((issue) => (
          <div key={issue.id} className="book-card">
            <div className="book-title">Выдача #{issue.id}</div>
            <div className="book-meta">
              Читатель: {issue.reader_id} | Экземпляр: {issue.copy_id} | Статус: {issue.status} | Срок: {issue.due_at}
            </div>
            {issue.status === "ISSUED" && (
              <button className="btn" disabled={returningId === issue.id} onClick={() => handleReturn(issue.id)}>
                {returningId === issue.id ? "Возврат..." : "Вернуть"}
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
