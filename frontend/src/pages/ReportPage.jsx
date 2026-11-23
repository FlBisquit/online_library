import { useCallback, useEffect, useState } from "react";
import { apiClient } from "../api/client";
import { Loading } from "../components/Loading";
import { EmptyState } from "../components/EmptyState";
import { ErrorMessage } from "../components/ErrorMessage";

const isoDate = (value) => value.toISOString().slice(0, 10);

const defaultPeriod = () => {
  const dateTo = new Date();
  const dateFrom = new Date(dateTo);
  dateFrom.setDate(dateFrom.getDate() - 29);
  return { date_from: isoDate(dateFrom), date_to: isoDate(dateTo) };
};

export const ReportPage = () => {
  const [filters, setFilters] = useState(defaultPeriod);
  const [applied, setApplied] = useState(defaultPeriod);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.get("/reports/books/", { params: applied });
      setRows(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [applied]);

  useEffect(() => {
    load();
  }, [load]);

  const setFilter = (key, value) => {
    setFilters((previous) => ({ ...previous, [key]: value }));
  };

  const handleApply = (event) => {
    event.preventDefault();
    if (filters.date_from > filters.date_to) {
      setError("Дата «с» не может быть позже даты «по».");
      return;
    }
    setApplied({ ...filters });
  };

  const handleReset = () => {
    const period = defaultPeriod();
    setFilters(period);
    setApplied(period);
  };

  const handleDownload = async () => {
    setDownloading(true);
    setError(null);
    try {
      // apiClient.download добавляет Bearer-токен к запросу.
      const blob = await apiClient.download("/reports/books/export/", {
        params: applied,
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `report_${applied.date_from}_${applied.date_to}.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e.message);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <section>
      <h3>Отчёт по книгам</h3>
      <form className="filter-row log-filters" onSubmit={handleApply}>
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
          Последние 30 дней
        </button>
        <button
          className="btn btn-secondary"
          type="button"
          disabled={downloading}
          onClick={handleDownload}
        >
          {downloading ? "Скачивание..." : "Скачать CSV"}
        </button>
      </form>

      <ErrorMessage message={error} />
      {loading && <Loading message="Загрузка отчёта..." />}
      {!loading && !error && rows.length === 0 && (
        <EmptyState message="За выбранный период данных нет." />
      )}
      {!loading && !error && rows.length > 0 && (
        <div className="table-wrap">
          <table className="log-table">
            <thead>
              <tr>
                <th>Книга</th>
                <th>Выдачи</th>
                <th>Просрочено</th>
                <th>Отмены</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.book_id}>
                  <td>{row.title}</td>
                  <td>{row.loans}</td>
                  <td>{row.overdue}</td>
                  <td>{row.cancellations}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
};
