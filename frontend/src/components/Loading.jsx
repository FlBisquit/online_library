export const Loading = ({ message = "Загрузка..." }) => (
  <div className="loading" role="status">
    {message}
  </div>
);
