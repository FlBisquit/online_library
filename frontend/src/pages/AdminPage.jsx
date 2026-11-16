import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export const AdminPage = () => {
  const { user } = useAuth();
  const [books, setBooks] = useState([]);
  const [readers, setReaders] = useState([]);
  const [loadingBooks, setLoadingBooks] = useState(false);
  const [loadingReaders, setLoadingReaders] = useState(false);
  const [error, setError] = useState(null);

  const [newBook, setNewBook] = useState({
    title: "",
    description: "",
    isbn: "",
    publication_year: "",
    publisher: "",
    authors: "",
    genres: "",
  });
  const [newCopy, setNewCopy] = useState({ book_id: "", inventory_number: "" });

  const loadBooks = useCallback(async () => {
    setLoadingBooks(true);
    setError(null);
    try {
      const data = await apiClient.get("/books/", { params: { limit: 100 } });
      setBooks(data.results ?? []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingBooks(false);
    }
  }, []);

  const loadReaders = useCallback(async () => {
    setLoadingReaders(true);
    setError(null);
    try {
      const data = await apiClient.get("/readers/", { params: { limit: 100 } });
      setReaders(data.results ?? []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingReaders(false);
    }
  }, []);

  useEffect(() => {
    loadBooks();
    loadReaders();
  }, [loadBooks, loadReaders]);

  const handleCreateBook = async (event) => {
    event.preventDefault();
    setError(null);
    try {
      await apiClient.post("/books/", {
        title: newBook.title,
        description: newBook.description || undefined,
        isbn: newBook.isbn,
        publication_year: newBook.publication_year ? Number(newBook.publication_year) : undefined,
        publisher: newBook.publisher || undefined,
        authors: (newBook.authors ?? "")
          .split(",")
          .map((v) => Number(v.trim()))
          .filter((v) => Number.isFinite(v)),
        genres: (newBook.genres ?? "")
          .split(",")
          .map((v) => Number(v.trim()))
          .filter((v) => Number.isFinite(v)),
      });
      setNewBook({ title: "", description: "", isbn: "", publication_year: "", publisher: "", authors: "", genres: "" });
      await loadBooks();
    } catch (e) {
      setError(e.message);
    }
  };

  const handleCreateCopy = async (event) => {
    event.preventDefault();
    setError(null);
    try {
      await apiClient.post(`/books/${newCopy.book_id}/copies/`, {
        inventory_number: newCopy.inventory_number,
        status: "AVAILABLE",
      });
      setNewCopy({ book_id: "", inventory_number: "" });
      await loadBooks();
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="page">
      <h2>Панель администратора</h2>
      {error && <div className="alert alert-error">{error}</div>}

      <section>
        <h3>Добавление книги</h3>
        <form onSubmit={handleCreateBook}>
          <input className="input" placeholder="Название" value={newBook.title} onChange={(e) => setNewBook({ ...newBook, title: e.target.value })} required />
          <input className="input" placeholder="ISBN" value={newBook.isbn} onChange={(e) => setNewBook({ ...newBook, isbn: e.target.value })} required />
          <input className="input" placeholder="Год публикации" value={newBook.publication_year} onChange={(e) => setNewBook({ ...newBook, publication_year: e.target.value })} />
          <input className="input" placeholder="Издательство" value={newBook.publisher} onChange={(e) => setNewBook({ ...newBook, publisher: e.target.value })} />
          <input className="input" placeholder="Авторы (id через запятую)" value={newBook.authors} onChange={(e) => setNewBook({ ...newBook, authors: e.target.value })} />
          <input className="input" placeholder="Жанры (id через запятую)" value={newBook.genres} onChange={(e) => setNewBook({ ...newBook, genres: e.target.value })} />
          <button className="btn" type="submit">Создать книгу</button>
        </form>
      </section>

      <section>
        <h3>Добавление экземпляра</h3>
        <form onSubmit={handleCreateCopy}>
          <select className="input" value={newCopy.book_id} onChange={(e) => setNewCopy({ ...newCopy, book_id: e.target.value })} required>
            <option value="">Выберите книгу</option>
            {books.map((book) => (
              <option key={book.id} value={book.id}>
                {book.title}
              </option>
            ))}
          </select>
          <input className="input" placeholder="Инвентарный номер" value={newCopy.inventory_number} onChange={(e) => setNewCopy({ ...newCopy, inventory_number: e.target.value })} required />
          <button className="btn" type="submit">Создать экземпляр</button>
        </form>
      </section>

      <section>
        <h3>Пользователи</h3>
        {loadingReaders && <div className="loading">Загрузка пользователей...</div>}
        {!loadingReaders && readers.length === 0 && <div className="empty">Пользователи не найдены.</div>}
        <div className="book-list">
          {readers.map((reader) => (
            <div key={reader.id} className="book-card">
              <div className="book-title">{reader.email}</div>
              <div className="book-meta">
                {reader.full_name} | Статус: {reader.status} | Роли: {(reader.groups ?? []).join(", ")}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
};
