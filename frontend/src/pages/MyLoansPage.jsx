import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Loading } from "../components/Loading";
import { EmptyState } from "../components/EmptyState";
import { ErrorMessage } from "../components/ErrorMessage";
import { Pagination } from "../components/Pagination";
import { extractGeneralError } from "../utils/formErrors";
import { formatDateTime, isOverdue, statusLabel } from "../i18n";

const HISTORY_PAGE_SIZE = 20;

export const MyLoansPage = () => {
  const { user } = useAuth();
  const [issues, setIssues] = useState([]);
  const [reservations, setReservations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [returningId, setReturningId] = useState(null);
  const [cancellingId, setCancellingId] = useState(null);
  const [historyPage, setHistoryPage] = useState(1);

  const loadIssues = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.get(`/readers/${user.id}/issues/`);
      setIssues(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(extractGeneralError(e));
    } finally {
      setLoading(false);
    }
  }, [user]);

  const loadReservations = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.get("/auth/me/reservations/");
      setReservations(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(extractGeneralError(e));
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    loadIssues();
  }, [loadIssues]);

  useEffect(() => {
    loadReservations();
  }, [loadReservations]);

  const handleReturn = async (issueId) => {
    setReturningId(issueId);
    setError(null);
    try {
      await apiClient.post(`/issues/${issueId}/return/`, {});
      await loadIssues();
      await loadReservations();
    } catch (e) {
      setError(extractGeneralError(e));
    } finally {
      setReturningId(null);
    }
  };

  const handleCancelReservation = async (reservationId) => {
    const reservation = reservations.find((item) => item.id === reservationId);
    const bookTitle = reservation?.book?.title ?? `Бронирование #${reservationId}`;
    if (!window.confirm(`Отменить бронирование на «${bookTitle}»?`)) {
      return;
    }
    setCancellingId(reservationId);
    setError(null);
    try {
      await apiClient.post(`/reservations/${reservationId}/cancel/`, {});
      await loadReservations();
    } catch (e) {
      setError(extractGeneralError(e));
    } finally {
      setCancellingId(null);
    }
  };

  const currentIssues = issues.filter(
    (issue) => issue.status === "ISSUED" || issue.status === "OVERDUE",
  );
  const historyIssues = issues.filter(
    (issue) => issue.status !== "ISSUED" && issue.status !== "OVERDUE",
  );
  const historyRows = historyIssues.slice(
    (historyPage - 1) * HISTORY_PAGE_SIZE,
    historyPage * HISTORY_PAGE_SIZE,
  );

  const totalHistoryPages = Math.max(1, Math.ceil(historyIssues.length / HISTORY_PAGE_SIZE));

  return (
    <div className="page">
      <h2>Мои выдачи</h2>
      <ErrorMessage message={error} />
      {loading && <Loading message="Загрузка выдач..." />}

      <section>
        <h3>Сейчас на руках</h3>
        {!loading && currentIssues.length === 0 && (
          <EmptyState message="Сейчас нет выданных книг." />
        )}
        <div className="book-list">
          {currentIssues.map((issue) => (
            <div key={issue.id} className="book-card">
              <div className="book-title">{issue.book?.title ?? `Выдача #${issue.id}`}</div>
              <div className="book-meta">
                Статус: {statusLabel(issue.status)}
                {isOverdue(issue) ? " — просрочено" : ""}
              </div>
              <div className="book-meta">Срок: {formatDateTime(issue.due_at)}</div>
              {isOverdue(issue) && <div className="book-meta">Книга просрочена.</div>}
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
      </section>

      <section>
        <h3>Мои очереди и брони</h3>
        {!loading && reservations.length === 0 && (
          <EmptyState message="У вас нет очередей или бронирований." />
        )}
        <div className="book-list">
          {reservations.map((reservation) => (
            <div key={reservation.id} className="book-card">
              <div className="book-title">{reservation.book?.title ?? `Бронирование #${reservation.id}`}</div>
              <div className="book-meta">
                {reservation.position != null
                  ? `Позиция: ${reservation.position} из ${reservation.total ?? 0}`
                  : "Позиция пока не определена"}
              </div>
              <div className="book-meta">Ожидание до: {formatDateTime(reservation.expires_at)}</div>
              <div className="book-meta">Статус: {statusLabel(reservation.status)}</div>
              {(reservation.status === "PENDING" || reservation.status === "ACTIVE") && (
                <button
                  className="btn"
                  disabled={cancellingId === reservation.id}
                  onClick={() => handleCancelReservation(reservation.id)}
                >
                  {cancellingId === reservation.id ? "Отмена..." : "Отменить"}
                </button>
              )}
            </div>
          ))}
        </div>
      </section>

      <section>
        <h3>История</h3>
        {!loading && historyRows.length === 0 && <EmptyState message="История выдач пуста." />}
        <div className="book-list">
          {historyRows.map((issue) => (
            <div key={issue.id} className="book-card">
              <div className="book-title">{issue.book?.title ?? `Выдача #${issue.id}`}</div>
              <div className="book-meta">
                Статус: {statusLabel(issue.status)} | Срок: {formatDateTime(issue.due_at)} | Выдано:{" "}
                {formatDateTime(issue.issued_at)} | Возвращено: {formatDateTime(issue.returned_at)}
              </div>
            </div>
          ))}
        </div>
        <Pagination
          page={historyPage}
          count={historyIssues.length}
          pageSize={HISTORY_PAGE_SIZE}
          hasPrevious={historyPage > 1}
          hasNext={historyPage < totalHistoryPages}
          disabled={loading}
          onPrevious={() => setHistoryPage((current) => Math.max(1, current - 1))}
          onNext={() => setHistoryPage((current) => Math.min(totalHistoryPages, current + 1))}
        />
      </section>
    </div>
  );
};
