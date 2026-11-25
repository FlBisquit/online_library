const dateTimeFormatter = new Intl.DateTimeFormat("ru-RU", {
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

export const formatDateTime = (value) => {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return dateTimeFormatter.format(date);
};

export const STATUS_LABELS = {
  ISSUED: "Выдано",
  RETURNED: "Возвращено",
  OVERDUE: "Просрочено",
  LOST: "Потеряно",
  RESERVED: "Зарезервировано",
  PENDING: "Ожидает",
  ACTIVE: "Активно",
  CANCELLED: "Отменено",
  EXPIRED: "Истекло",
};

export const statusLabel = (status) => STATUS_LABELS[status] ?? status;

export const isOverdue = (issue) => {
  if (issue?.status === "OVERDUE") return true;
  const dueAt = issue?.due_at;
  if (!dueAt) return false;
  const dueDate = new Date(dueAt);
  const now = new Date();
  return !Number.isNaN(dueDate.getTime()) && dueDate.getTime() < now.getTime();
};
