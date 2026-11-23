export const Pagination = ({
  page,
  count,
  pageSize = 20,
  hasPrevious,
  hasNext,
  disabled = false,
  onPrevious,
  onNext,
}) => {
  const totalPages = Math.max(1, Math.ceil((count ?? 0) / pageSize));
  return (
    <div className="pagination">
      <button
        className="btn btn-secondary"
        disabled={disabled || !hasPrevious}
        onClick={onPrevious}
      >
        ← Назад
      </button>
      <span>
        Страница {page} из {totalPages} (записей: {count ?? 0})
      </span>
      <button
        className="btn btn-secondary"
        disabled={disabled || !hasNext}
        onClick={onNext}
      >
        Вперёд →
      </button>
    </div>
  );
};
