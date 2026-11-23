export const EmptyState = ({ message = "Список пуст." }) => (
  <div className="empty" role="status">
    {message}
  </div>
);
