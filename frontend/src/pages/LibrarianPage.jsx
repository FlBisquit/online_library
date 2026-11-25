import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Loading } from "../components/Loading";
import { EmptyState } from "../components/EmptyState";
import { ErrorMessage } from "../components/ErrorMessage";
import { ActionLogPage } from "./ActionLogPage";
import { extractGeneralError } from "../utils/formErrors";
import { formatDateTime, statusLabel } from "../i18n";

export const LibrarianPage = () => {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState("issues");
  const [issues, setIssues] = useState([]);
  const [waiting, setWaiting] = useState([]);
  const [loadingIssues, setLoadingIssues] = useState(false);
  const [loadingWaiting, setLoadingWaiting] = useState(false);
  const [error, setError] = useState(null);
  const [dueFilter, setDueFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [issueSearch, setIssueSearch] = useState("");
  const [returningId, setReturningId] = useState(null);
  const [markingLostId, setMarkingLostId] = useState(null);

  const [readerQuery, setReaderQuery] = useState("");
  const [readerOptions, setReaderOptions] = useState([]);
  const [readerId, setReaderId] = useState(null);
  const [searchingReaders, setSearchingReaders] = useState(false);
  const [readersSearched, setReadersSearched] = useState(false);
  const [bookQuery, setBookQuery] = useState("");
  const [bookOptions, setBookOptions] = useState([]);
  const [bookId, setBookId] = useState(null);
  const [searchingBooks, setSearchingBooks] = useState(false);
  const [booksSearched, setBooksSearched] = useState(false);
  const [copies, setCopies] = useState([]);
  const [copyId, setCopyId] = useState(null);
  const [busy, setBusy] = useState(false);

  const loadIssues = useCallback(async () => {
    setLoadingIssues(true);
    setError(null);
    try {
      const data = await apiClient.get("/issues/", {
        params: {
          due: dueFilter || undefined,
          status: statusFilter || undefined,
          search: issueSearch || undefined,
          limit: 50,
        },
      });
      setIssues(data.results ?? []);
    } catch (e) {
      setError(extractGeneralError(e));
    } finally {
      setLoadingIssues(false);
    }
  }, [dueFilter, statusFilter, issueSearch]);

  const loadWaiting = useCallback(async () => {
    setLoadingWaiting(true);
    setError(null);
    try {
      const data = await apiClient.get("/reservations/", { params: { status: "ACTIVE", limit: 50 } });
      setWaiting(data.results ?? []);
    } catch (e) {
      setError(extractGeneralError(e));
    } finally {
      setLoadingWaiting(false);
    }
  }, []);

  useEffect(() => {
    loadIssues();
  }, [loadIssues]);

  useEffect(() => {
    loadWaiting();
  }, [loadWaiting]);

  useEffect(() => {
    if (!bookId) {
      setCopies([]);
      return;
    }
    let cancelled = false;
    const loadCopies = async () => {
      try {
        const data = await apiClient.get(`/books/${bookId}/copies/`, { params: { limit: 100 } });
        if (!cancelled) setCopies(data.results ?? []);
      } catch (e) {
        if (!cancelled) setError(extractGeneralError(e));
      }
    };
    loadCopies();
    return () => {
      cancelled = true;
    };
  }, [bookId]);

  const searchReaders = async () => {
    setSearchingReaders(true);
    setReadersSearched(true);
    setError(null);
    try {
      const data = await apiClient.get("/readers/search/", {
        params: { search: readerQuery, limit: 20 },
      });
      setReaderOptions(data.results ?? []);
    } catch (e) {
      setReaderOptions([]);
      setError(extractGeneralError(e));
    } finally {
      setSearchingReaders(false);
    }
  };

  const searchBooks = async () => {
    setSearchingBooks(true);
    setBooksSearched(true);
    setError(null);
    try {
      const data = await apiClient.get("/books/", { params: { search: bookQuery, limit: 20 } });
      setBookOptions(data.results ?? []);
    } catch (e) {
      setBookOptions([]);
      setError(extractGeneralError(e));
    } finally {
      setSearchingBooks(false);
    }
  };

  const handleIssue = async (event) => {
    event.preventDefault();
    if (!readerId || !copyId) {
      setError("Выберите читателя и экземпляр книги.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const copiesResponse = await apiClient.get(`/books/${bookId}/copies/`, { params: { limit: 100 } });
      const selectedCopy = (copiesResponse.results ?? []).find((item) => item.id === copyId);
      let finalReaderId = readerId;
      if (selectedCopy?.status === "RESERVED") {
        const waitingResponse = await apiClient.get("/reservations/", { params: { status: "ACTIVE", limit: 100 } });
        const reservation = (waitingResponse.results ?? []).find(
          (item) => item.copy?.inventory_number === selectedCopy.inventory_number,
        );
        if (reservation) finalReaderId = reservation.reader_id;
      }
      await apiClient.post("/issues/", { reader_id: finalReaderId, copy_id: copyId });
      await loadIssues();
      await loadWaiting();
    } catch (e) {
      setError(extractGeneralError(e));
    } finally {
      setBusy(false);
    }
  };

  const handleReturn = async (issueId) => {
    setReturningId(issueId);
    setError(null);
    try {
      await apiClient.post(`/issues/${issueId}/return/`, {});
      await loadIssues();
      await loadWaiting();
    } catch (e) {
      setError(extractGeneralError(e));
    } finally {
      setReturningId(null);
    }
  };

  const handleMarkLost = async (issueId) => {
    setMarkingLostId(issueId);
    setError(null);
    try {
      await apiClient.post(`/issues/${issueId}/mark-lost/`, {});
      await loadIssues();
      await loadWaiting();
    } catch (e) {
      setError(extractGeneralError(e));
    } finally {
      setMarkingLostId(null);
    }
  };

  const renderBookMeta = (issue) => (
    <>
      <div className="book-meta">Книга: {issue.book?.title ?? `Выдача #${issue.id}`}</div>
      <div className="book-meta">Читатель: {issue.reader?.full_name ?? `Читатель #${issue.reader_id}`}</div>
      <div className="book-meta">Экземпляр: {issue.copy?.inventory_number ?? `Экземпляр #${issue.copy_id}`}</div>
      <div className="book-meta">Статус: {statusLabel(issue.status)}</div>
      <div className="book-meta">Срок: {formatDateTime(issue.due_at)}</div>
    </>
  );

  return (
    <div className="page">
      <h2>Панель библиотекаря</h2>
      <div className="sub-tabs">
        <button
          className={`nav-item ${activeTab === "issues" ? "active" : ""}`}
          onClick={() => setActiveTab("issues")}
        >
          Выдачи
        </button>
        <button
          className={`nav-item ${activeTab === "issues" && dueFilter === "today" ? "active" : ""}`}
          onClick={() => {
            setDueFilter("today");
            setActiveTab("issues");
          }}
        >
          Выдачи на сегодня
        </button>
        <button
          className={`nav-item ${activeTab === "issues" && dueFilter === "overdue" ? "active" : ""}`}
          onClick={() => {
            setDueFilter("overdue");
            setActiveTab("issues");
          }}
        >
          Просроченные
        </button>
        <button
          className={`nav-item ${activeTab === "waiting" ? "active" : ""}`}
          onClick={() => setActiveTab("waiting")}
        >
          Ждут выдачи
        </button>
        <button
          className={`nav-item ${activeTab === "log" ? "active" : ""}`}
          onClick={() => setActiveTab("log")}
        >
          Журнал
        </button>
      </div>

      {error && <ErrorMessage message={error} />}

      {activeTab === "issues" && (
        <>
          <section>
            <h3>Выдать книгу</h3>
            <form className="admin-form" onSubmit={handleIssue}>
              <label className="multi-label">
                Читатель (email или ФИО)
                <input
                  className="input"
                  value={readerQuery}
                  onChange={(event) => setReaderQuery(event.target.value)}
                  placeholder="Иванов Иван Иванович"
                />
              </label>
              <button
                className="btn btn-secondary"
                type="button"
                disabled={searchingReaders}
                onClick={searchReaders}
              >
                {searchingReaders ? "Поиск..." : "Найти читателя"}
              </button>
              {searchingReaders && <div className="loading">Поиск читателей...</div>}
              {readersSearched && !searchingReaders && readerOptions.length === 0 && (
                <div className="empty">Читатели не найдены.</div>
              )}
              <select className="input" value={readerId} onChange={(event) => setReaderId(event.target.value)}>
                <option value="">Выберите читателя</option>
                {readerOptions.map((reader) => (
                  <option key={reader.id} value={reader.id}>
                    {reader.full_name} ({reader.email})
                    {reader.status === "BLOCKED" ? " — заблокирован" : ""}
                  </option>
                ))}
              </select>

              <label className="multi-label">
                Книга
                <input
                  className="input"
                  value={bookQuery}
                  onChange={(event) => setBookQuery(event.target.value)}
                  placeholder="Название книги"
                />
              </label>
              <button
                className="btn btn-secondary"
                type="button"
                disabled={searchingBooks}
                onClick={searchBooks}
              >
                {searchingBooks ? "Поиск..." : "Найти книгу"}
              </button>
              {searchingBooks && <div className="loading">Поиск книг...</div>}
              {booksSearched && !searchingBooks && bookOptions.length === 0 && (
                <div className="empty">Книги не найдены.</div>
              )}
              <select className="input" value={bookId} onChange={(event) => setBookId(event.target.value)}>
                <option value="">Выберите книгу</option>
                {bookOptions.map((book) => (
                  <option key={book.id} value={book.id}>
                    {book.title}
                  </option>
                ))}
              </select>

              {bookId && (
                <>
                  <label className="multi-label">
                    Экземпляр
                    <select className="input" value={copyId} onChange={(event) => setCopyId(event.target.value)}>
                      <option value="">Выберите экземпляр</option>
                      {copies.map((copy) => (
                        <option key={copy.id} value={copy.id}>
                          {copy.inventory_number} ({copy.status})
                        </option>
                      ))}
                    </select>
                  </label>
                  {busy && <div className="loading">Выдача книги...</div>}
                </>
              )}

              <button className="btn" type="submit" disabled={busy || !readerId || !copyId}>
                Выдать книгу
              </button>
            </form>
          </section>

          <section>
            <h3>
              {dueFilter === "today"
                ? "Выдачи на сегодня"
                : dueFilter === "overdue"
                  ? "Просроченные"
                  : "Выдачи"}
            </h3>
            <form
              className="filter-row log-filters"
              onSubmit={(event) => {
                event.preventDefault();
                loadIssues();
              }}
            >
              <input
                className="input"
                value={issueSearch}
                onChange={(event) => setIssueSearch(event.target.value)}
                placeholder="Поиск по книге, читателю или экземпляру"
              />
              <select className="input" value={dueFilter} onChange={(event) => setDueFilter(event.target.value)}>
                <option value="">Все сроки</option>
                <option value="today">Выдачи на сегодня</option>
                <option value="overdue">Просроченные</option>
              </select>
              <select className="input" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                <option value="">Все статусы</option>
                <option value="ISSUED">Выдано</option>
                <option value="RETURNED">Возвращено</option>
                <option value="OVERDUE">Просрочено</option>
                <option value="LOST">Потеряно</option>
              </select>
              <button className="btn" type="submit">
                Применить
              </button>
              <button
                className="btn btn-secondary"
                type="button"
                onClick={() => {
                  setIssueSearch("");
                  setDueFilter("");
                  setStatusFilter("");
                }}
              >
                Сбросить
              </button>
            </form>

            {loadingIssues && <Loading message="Загрузка выдач..." />}
            {!loadingIssues && issues.length === 0 && (
              <EmptyState
                message={
                  dueFilter === "today"
                    ? "Выдач на сегодня нет."
                    : dueFilter === "overdue"
                      ? "Просроченных выдач нет."
                      : "Выдачи не найдены."
                }
              />
            )}
            <div className="book-list">
              {issues.map((issue) => (
                <div key={issue.id} className="book-card">
                  <div className="book-title">{issue.book?.title ?? `Выдача #${issue.id}`}</div>
                  {renderBookMeta(issue)}
                  <div className="admin-actions">
                    {(issue.status === "ISSUED" || issue.status === "OVERDUE") && (
                      <>
                        <button
                          className="btn"
                          disabled={returningId === issue.id}
                          onClick={() => handleReturn(issue.id)}
                        >
                          {returningId === issue.id ? "Возврат..." : "Вернуть"}
                        </button>
                        <button
                          className="btn btn-secondary"
                          disabled={markingLostId === issue.id}
                          onClick={() => handleMarkLost(issue.id)}
                        >
                          {markingLostId === issue.id ? "Потеряна..." : "Потеряна"}
                        </button>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </section>
        </>
      )}

      {activeTab === "waiting" && (
        <section>
          <h3>Ждут выдачи</h3>
          {loadingWaiting && <Loading message="Загрузка ожиданий..." />}
          {!loadingWaiting && waiting.length === 0 && <EmptyState message="Сейчас никто не ждёт выдачи." />}
          <div className="book-list">
            {waiting.map((reservation) => (
              <div key={reservation.id} className="book-card">
                <div className="book-title">{reservation.book?.title ?? `Бронирование #${reservation.id}`}</div>
                <div className="book-meta">Читатель: {reservation.reader?.full_name ?? `Читатель #${reservation.reader_id}`}</div>
                <div className="book-meta">
                  Позиция: {reservation.position != null ? `${reservation.position} из ${reservation.total ?? 0}` : "—"}
                </div>
                <div className="book-meta">Статус: {statusLabel(reservation.status)}</div>
                <div className="book-meta">Ожидание до: {formatDateTime(reservation.expires_at)}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {activeTab === "log" && <ActionLogPage readOnly />}
    </div>
  );
};
