import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export const MyLoansPage = () => {
  const { user } = useAuth();
  const [issues, setIssues] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [returningId, setReturningId] = useState(null);

  const loadIssues = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.get(`/readers/${user.id}/issues/`);
      setIssues(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    loadIssues();
  }, [loadIssues]);

  const handleReturn = async (issueId) => {
    setReturningId(issueId);
    setError(null);
    try {
      await apiClient.post(`/issues/${issueId}/return/`, {});
      await loadIssues();
    } catch (e) {
      setError(e.message);
    } finally {
      setReturningId(null);
    }
  };

  const active = issues.filter((issue) => issue.status === "ISSUED");
  const history = issues.filter((issue) => issue.status !== "ISSUED");

  return (
    <div className="page">
      <h2>Мои выдачи</h2>
      {loading && <div className="loading">Загрузка выдач...</div>}
      {error && <div className="alert alert-error">{error}</div>}
      {!loading && !error && issues.length === 0 && <div className="empty">У вас нет выдач.</div>}

      {active.length > 0 && (
        <>
          <h3>Текущие выдачи</h3>
          <div className="book-list">
            {active.map((issue) => (
              <div key={issue.id} className="book-card">
                <div className="book-title">Выдача #{issue.id}</div>
                <div className="book-meta">
                  Экземпляр: {issue.copy_id} | Статус: {issue.status} | Срок: {issue.due_at}
                </div>
                <button
                  className="btn"
                  disabled={returningId === issue.id}
                  onClick={() => handleReturn(issue.id)}
                >
                  {returningId === issue.id ? "Возврат..." : "Вернуть книгу"}
                </button>
              </div>
            ))}
          </div>
        </>
      )}

      {history.length > 0 && (
        <>
          <h3>История выдач</h3>
          <div className="book-list">
            {history.map((issue) => (
              <div key={issue.id} className="book-card">
                <div className="book-title">Выдача #{issue.id}</div>
                <div className="book-meta">
                  Экземпляр: {issue.copy_id} | Статус: {issue.status} | Выдано: {issue.issued_at} | Возвращено:{" "}
                  {issue.returned_at}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
};
