import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../api/client";
import { Loading } from "../components/Loading";
import { EmptyState } from "../components/EmptyState";
import { ErrorMessage } from "../components/ErrorMessage";

export const CatalogPage = () => {
  const [books, setBooks] = useState([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedBookId, setSelectedBookId] = useState(null);
  const [bookDetail, setBookDetail] = useState(null);
  const [copies, setCopies] = useState([]);

  const loadBooks = useCallback(async (pageNumber, searchValue) => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.get("/books/", {
        params: { page: pageNumber, limit: 20, search: searchValue || undefined },
      });
      setBooks(data.results ?? []);
      setCount(data.count ?? 0);
      setPage(data.next ? pageNumber + 1 : pageNumber);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadBooks(page, search);
  }, [page, search, loadBooks]);

  useEffect(() => {
    if (!selectedBookId) {
      setBookDetail(null);
      setCopies([]);
      return;
    }
    const loadDetail = async () => {
      try {
        const [book, copyData] = await Promise.all([
          apiClient.get(`/books/${selectedBookId}/`),
          apiClient.get(`/books/${selectedBookId}/copies/`),
        ]);
        setBookDetail(book);
        setCopies(copyData.results ?? []);
      } catch (e) {
        setError(e.message);
      }
    };
    loadDetail();
  }, [selectedBookId]);

  const handleSearch = (value) => {
    setSearch(value);
    setPage(1);
  };

  const totalPages = Math.max(1, Math.ceil(count / 20));

  return (
    <div className="page">
      <h2>Каталог книг</h2>
      <input
        className="input"
        placeholder="Поиск по названию, ISBN, описанию..."
        value={search}
        onChange={(e) => handleSearch(e.target.value)}
      />
      {loading && <Loading message="Загрузка каталога..." />}
      <ErrorMessage message={error} />
      {!loading && !error && books.length === 0 && <EmptyState message="Книги не найдены." />}
      <div className="book-list">
        {books.map((book) => (
          <button key={book.id} className="book-card" onClick={() => setSelectedBookId(book.id)}>
            <div className="book-title">{book.title}</div>
            <div className="book-meta">
              {book.publication_year && `Серия: ${book.publication_year}. `}
              ISBN: {book.isbn}
            </div>
          </button>
        ))}
      </div>
      <div className="pagination">
        <button className="btn" disabled={page <= 1} onClick={() => setPage(page - 1)}>
          Назад
        </button>
        <span>
          Страница {page} из {totalPages}
        </span>
        <button className="btn" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
          Далее
        </button>
      </div>

      {selectedBookId && (
        <div className="book-detail">
          {bookDetail && (
            <div className="book-detail-card">
              <h3>{bookDetail.title}</h3>
              <p>{bookDetail.description}</p>
              <p>Издательство: {bookDetail.publisher}</p>
            </div>
          )}
          <h4>Экземпляры книги</h4>
          {copies.length === 0 && <EmptyState message="Экземпляры не найдены." />}
          <div className="book-list">
            {copies.map((copy) => (
              <div key={copy.id} className="book-card">
                <div className="book-title">{copy.inventory_number}</div>
                <div className="book-meta">Статус: {copy.status}</div>
              </div>
            ))}
          </div>
          <button className="btn" onClick={() => setSelectedBookId(null)}>
            Закрыть
          </button>
        </div>
      )}
    </div>
  );
};
