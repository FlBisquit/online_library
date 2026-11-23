import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../api/client";
import { Loading } from "../components/Loading";
import { EmptyState } from "../components/EmptyState";
import { ErrorMessage } from "../components/ErrorMessage";
import { Pagination } from "../components/Pagination";
import { extractFieldErrors, extractGeneralError } from "../utils/formErrors";

const COPY_STATUSES = ["AVAILABLE", "ISSUED", "RESERVED", "LOST", "RETIRED"];
const SERVICE_COPY_STATUSES = ["ISSUED", "RESERVED"];

const EMPTY_BOOK = {
  title: "",
  isbn: "",
  description: "",
  publication_year: "",
  publisher: "",
  authors: [],
  genres: [],
};

const FieldError = ({ errors, name }) =>
  errors[name] ? <div className="field-error">{errors[name]}</div> : null;

const ReferenceSection = ({
  title,
  nameKey,
  items,
  form,
  errors,
  onChange,
  onSubmit,
  onEdit,
  onDelete,
  placeholder,
}) => (
  <section className="reference-section">
    <h4>{title}</h4>
    <form className="reference-form" onSubmit={onSubmit}>
      <input
        className="input"
        placeholder={placeholder}
        value={form[nameKey]}
        onChange={(event) => onChange(nameKey, event.target.value)}
        required
      />
      <button className="btn" type="submit">
        {form.id ? "Сохранить" : "Добавить"}
      </button>
      {form.id && (
        <button className="btn btn-secondary" type="button" onClick={() => onChange("id", null)}>
          Отмена
        </button>
      )}
    </form>
    <FieldError errors={errors} name={nameKey} />
    <div className="reference-list">
      {items.map((item) => (
        <div key={item.id} className="reference-item">
          <span>{item[nameKey]}</span>
          <span className="admin-actions">
            <button className="btn btn-secondary" type="button" onClick={() => onEdit(item)}>
              Изменить
            </button>
            <button className="btn btn-secondary" type="button" onClick={() => onDelete(item)}>
              Удалить
            </button>
          </span>
        </div>
      ))}
    </div>
  </section>
);

export const BooksAdminPage = () => {
  const [books, setBooks] = useState({ results: [], count: 0, next: null, previous: null });
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  const [authors, setAuthors] = useState([]);
  const [genres, setGenres] = useState([]);
  const [bookForm, setBookForm] = useState(EMPTY_BOOK);
  const [editingBookId, setEditingBookId] = useState(null);
  const [bookErrors, setBookErrors] = useState({});
  const [authorForm, setAuthorForm] = useState({ id: null, full_name: "" });
  const [genreForm, setGenreForm] = useState({ id: null, name: "" });
  const [referenceErrors, setReferenceErrors] = useState({});
  const [selectedBookId, setSelectedBookId] = useState(null);
  const [copies, setCopies] = useState([]);
  const [copyForm, setCopyForm] = useState({ inventory_number: "" });
  const [copyErrors, setCopyErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const loadBooks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.get("/books/", {
        params: { search: appliedSearch || undefined, page, limit: 20 },
      });
      setBooks(data);
    } catch (e) {
      setError(extractGeneralError(e));
    } finally {
      setLoading(false);
    }
  }, [appliedSearch, page]);

  const loadReferences = useCallback(async () => {
    try {
      const [authorData, genreData] = await Promise.all([
        apiClient.get("/authors/", { params: { limit: 100 } }),
        apiClient.get("/genres/", { params: { limit: 100 } }),
      ]);
      setAuthors(authorData.results ?? []);
      setGenres(genreData.results ?? []);
    } catch (e) {
      setError(extractGeneralError(e));
    }
  }, []);

  const loadCopies = useCallback(async (bookId) => {
    if (!bookId) {
      setCopies([]);
      return;
    }
    try {
      const data = await apiClient.get(`/books/${bookId}/copies/`, { params: { limit: 100 } });
      setCopies(data.results ?? []);
    } catch (e) {
      setError(extractGeneralError(e));
    }
  }, []);

  useEffect(() => {
    loadBooks();
  }, [loadBooks]);

  useEffect(() => {
    loadReferences();
  }, [loadReferences]);

  useEffect(() => {
    loadCopies(selectedBookId);
  }, [selectedBookId, loadCopies, books]);

  const setBookField = (key, value) => {
    setBookForm((previous) => ({ ...previous, [key]: value }));
  };

  const startEditBook = (book) => {
    setEditingBookId(book.id);
    setBookForm({
      title: book.title ?? "",
      isbn: book.isbn ?? "",
      description: book.description ?? "",
      publication_year: book.publication_year ?? "",
      publisher: book.publisher ?? "",
      authors: (book.authors ?? []).map(String),
      genres: (book.genres ?? []).map(String),
    });
    setBookErrors({});
    setSelectedBookId(book.id);
  };

  const resetBookForm = () => {
    setEditingBookId(null);
    setBookForm(EMPTY_BOOK);
    setBookErrors({});
  };

  const handleBookSubmit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setBookErrors({});
    try {
      const payload = {
        title: bookForm.title,
        isbn: bookForm.isbn,
        description: bookForm.description || undefined,
        publication_year: bookForm.publication_year
          ? Number(bookForm.publication_year)
          : undefined,
        publisher: bookForm.publisher || undefined,
        authors: bookForm.authors.map(Number),
        genres: bookForm.genres.map(Number),
      };
      if (editingBookId) {
        await apiClient.patch(`/books/${editingBookId}/`, payload);
      } else {
        await apiClient.post("/books/", payload);
      }
      resetBookForm();
      await loadBooks();
    } catch (e) {
      setBookErrors(extractFieldErrors(e));
      setError(extractGeneralError(e));
    } finally {
      setBusy(false);
    }
  };

  const handleBookDelete = async (book) => {
    if (!window.confirm(`Удалить книгу «${book.title}»?`)) return;
    setBusy(true);
    setError(null);
    try {
      await apiClient.delete(`/books/${book.id}/`);
      if (selectedBookId === book.id) setSelectedBookId(null);
      if (editingBookId === book.id) resetBookForm();
      await loadBooks();
    } catch (e) {
      setError(extractGeneralError(e));
    } finally {
      setBusy(false);
    }
  };

  const handleCopyCreate = async (event) => {
    event.preventDefault();
    if (!selectedBookId) return;
    setBusy(true);
    setError(null);
    setCopyErrors({});
    try {
      await apiClient.post(`/books/${selectedBookId}/copies/`, {
        inventory_number: copyForm.inventory_number,
        status: "AVAILABLE",
      });
      setCopyForm({ inventory_number: "" });
      await loadCopies(selectedBookId);
    } catch (e) {
      setCopyErrors(extractFieldErrors(e));
      setError(extractGeneralError(e));
    } finally {
      setBusy(false);
    }
  };

  const handleCopyStatus = async (copy, status) => {
    setBusy(true);
    setError(null);
    try {
      await apiClient.patch(`/copies/${copy.id}/`, { status });
      await loadCopies(selectedBookId);
    } catch (e) {
      setError(extractGeneralError(e));
    } finally {
      setBusy(false);
    }
  };

  const handleCopyDelete = async (copy) => {
    if (!window.confirm(`Удалить экземпляр ${copy.inventory_number}?`)) return;
    setBusy(true);
    setError(null);
    try {
      await apiClient.delete(`/copies/${copy.id}/`);
      await loadCopies(selectedBookId);
    } catch (e) {
      setError(extractGeneralError(e));
    } finally {
      setBusy(false);
    }
  };

  const submitReference = async (kind, form) => {
    const path = kind === "author" ? "/authors/" : "/genres/";
    const nameKey = kind === "author" ? "full_name" : "name";
    const setter = kind === "author" ? setAuthorForm : setGenreForm;
    setBusy(true);
    setError(null);
    setReferenceErrors({});
    try {
      const payload = { [nameKey]: form[nameKey] };
      if (form.id) await apiClient.patch(`${path}${form.id}/`, payload);
      else await apiClient.post(path, payload);
      setter({ id: null, [nameKey]: "" });
      await loadReferences();
    } catch (e) {
      setReferenceErrors(extractFieldErrors(e));
      setError(extractGeneralError(e));
    } finally {
      setBusy(false);
    }
  };

  const deleteReference = async (kind, item) => {
    const path = kind === "author" ? "/authors/" : "/genres/";
    const label = kind === "author" ? item.full_name : item.name;
    if (!window.confirm(`Удалить «${label}»?`)) return;
    setBusy(true);
    setError(null);
    try {
      await apiClient.delete(`${path}${item.id}/`);
      await loadReferences();
    } catch (e) {
      setError(extractGeneralError(e));
    } finally {
      setBusy(false);
    }
  };

  const authorName = (id) => authors.find((item) => item.id === id)?.full_name ?? `#${id}`;
  const genreName = (id) => genres.find((item) => item.id === id)?.name ?? `#${id}`;

  return (
    <div>
      <section>
        <h3>{editingBookId ? "Редактирование книги" : "Добавление книги"}</h3>
        <form className="admin-form" onSubmit={handleBookSubmit}>
          <input className="input" placeholder="Название" value={bookForm.title} onChange={(e) => setBookField("title", e.target.value)} required />
          <FieldError errors={bookErrors} name="title" />
          <input className="input" placeholder="ISBN" value={bookForm.isbn} onChange={(e) => setBookField("isbn", e.target.value)} required />
          <FieldError errors={bookErrors} name="isbn" />
          <input className="input" placeholder="Год публикации" value={bookForm.publication_year} onChange={(e) => setBookField("publication_year", e.target.value)} />
          <FieldError errors={bookErrors} name="publication_year" />
          <input className="input" placeholder="Издательство" value={bookForm.publisher} onChange={(e) => setBookField("publisher", e.target.value)} />
          <textarea className="input" placeholder="Описание" value={bookForm.description} onChange={(e) => setBookField("description", e.target.value)} />
          <label className="multi-label">
            Авторы
            <select
              className="input"
              multiple
              value={bookForm.authors}
              onChange={(e) => setBookField("authors", Array.from(e.target.selectedOptions).map((option) => option.value))}
            >
              {authors.map((author) => (
                <option key={author.id} value={String(author.id)}>{author.full_name}</option>
              ))}
            </select>
          </label>
          <FieldError errors={bookErrors} name="authors" />
          <label className="multi-label">
            Жанры
            <select
              className="input"
              multiple
              value={bookForm.genres}
              onChange={(e) => setBookField("genres", Array.from(e.target.selectedOptions).map((option) => option.value))}
            >
              {genres.map((genre) => (
                <option key={genre.id} value={String(genre.id)}>{genre.name}</option>
              ))}
            </select>
          </label>
          <FieldError errors={bookErrors} name="genres" />
          <div className="admin-actions">
            <button className="btn" type="submit" disabled={busy}>
              {editingBookId ? "Сохранить" : "Создать книгу"}
            </button>
            {editingBookId && (
              <button className="btn btn-secondary" type="button" onClick={resetBookForm}>
                Отмена
              </button>
            )}
          </div>
        </form>
      </section>

      <section>
        <h3>Книги</h3>
        <form
          className="filter-row log-filters"
          onSubmit={(event) => {
            event.preventDefault();
            setPage(1);
            setAppliedSearch(search);
          }}
        >
          <input className="input" placeholder="Поиск по названию" value={search} onChange={(e) => setSearch(e.target.value)} />
          <button className="btn" type="submit">Найти</button>
        </form>
        <ErrorMessage message={error} />
        {loading && <Loading message="Загрузка книг..." />}
        {!loading && books.results.length === 0 && <EmptyState message="Книги не найдены." />}
        {!loading && books.results.length > 0 && (
          <div className="table-wrap">
            <table className="log-table">
              <thead>
                <tr>
                  <th>Название</th>
                  <th>ISBN</th>
                  <th>Авторы</th>
                  <th>Жанры</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {books.results.map((book) => (
                  <tr key={book.id}>
                    <td>{book.title}</td>
                    <td>{book.isbn}</td>
                    <td>{(book.authors ?? []).map(authorName).join(", ") || "—"}</td>
                    <td>{(book.genres ?? []).map(genreName).join(", ") || "—"}</td>
                    <td>
                      <div className="admin-actions">
                        <button className="btn btn-secondary" type="button" onClick={() => startEditBook(book)}>Изменить</button>
                        <button className="btn btn-secondary" type="button" onClick={() => setSelectedBookId(book.id)}>Экземпляры</button>
                        <button className="btn btn-secondary" type="button" disabled={busy} onClick={() => handleBookDelete(book)}>Удалить</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pagination
          page={page}
          count={books.count}
          pageSize={20}
          hasPrevious={Boolean(books.previous)}
          hasNext={Boolean(books.next)}
          disabled={loading}
          onPrevious={() => setPage((current) => Math.max(1, current - 1))}
          onNext={() => setPage((current) => current + 1)}
        />
      </section>

      <section>
        <h3>Экземпляры</h3>
        {!selectedBookId && <EmptyState message="Выберите книгу, чтобы управлять экземплярами." />}
        {selectedBookId && (
          <>
            <form className="reference-form" onSubmit={handleCopyCreate}>
              <input className="input" placeholder="Инвентарный номер" value={copyForm.inventory_number} onChange={(e) => setCopyForm({ inventory_number: e.target.value })} required />
              <button className="btn" type="submit" disabled={busy}>Добавить экземпляр</button>
            </form>
            <FieldError errors={copyErrors} name="inventory_number" />
            {copies.length === 0 && <EmptyState message="Экземпляров нет." />}
            <div className="reference-list">
              {copies.map((copy) => (
                <div key={copy.id} className="reference-item">
                  <span>{copy.inventory_number}</span>
                  <span className="admin-actions">
                    <select
                      className="input status-select"
                      value={copy.status}
                      disabled={busy}
                      onChange={(e) => handleCopyStatus(copy, e.target.value)}
                    >
                      {COPY_STATUSES.map((itemStatus) => (
                        <option
                          key={itemStatus}
                          value={itemStatus}
                          disabled={
                            SERVICE_COPY_STATUSES.includes(itemStatus) ||
                            (itemStatus === "AVAILABLE" &&
                              SERVICE_COPY_STATUSES.includes(copy.status))
                          }
                        >
                          {itemStatus}
                        </option>
                      ))}
                    </select>
                    <button className="btn btn-secondary" type="button" disabled={busy} onClick={() => handleCopyDelete(copy)}>Удалить</button>
                  </span>
                </div>
              ))}
            </div>
          </>
        )}
      </section>

      <div className="reference-grid">
        <ReferenceSection
          title="Авторы"
          nameKey="full_name"
          items={authors}
          form={authorForm}
          errors={referenceErrors}
          placeholder="ФИО автора"
          onChange={(key, value) => setAuthorForm((previous) => ({ ...previous, [key]: value }))}
          onSubmit={(event) => {
            event.preventDefault();
            submitReference("author", authorForm);
          }}
          onEdit={(item) => setAuthorForm({ id: item.id, full_name: item.full_name })}
          onDelete={(item) => deleteReference("author", item)}
        />
        <ReferenceSection
          title="Жанры"
          nameKey="name"
          items={genres}
          form={genreForm}
          errors={referenceErrors}
          placeholder="Название жанра"
          onChange={(key, value) => setGenreForm((previous) => ({ ...previous, [key]: value }))}
          onSubmit={(event) => {
            event.preventDefault();
            submitReference("genre", genreForm);
          }}
          onEdit={(item) => setGenreForm({ id: item.id, name: item.name })}
          onDelete={(item) => deleteReference("genre", item)}
        />
      </div>
    </div>
  );
};
