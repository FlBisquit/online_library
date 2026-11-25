# Conventions

## Backend (Django / DRF)

- Имя и структура моделей, миграции, сериализаторы, views follow Django REST Framework conventions.
- Бизнес-логика выдачи/возврата/очереди — в `library/services.py`, транзакции с `select_for_update`.
- Роли: группы `reader`, `librarian`, `admin`; проверки через `library/permissions.py`.
- Статусы: `TextChoices` внутри моделей, CHECK-ограничения.
- Тесты: `library/tests.py`, DRF APITestCase + APIClient, MySQL.

## Frontend (React)

- Компоненты страниц в `frontend/src/pages/`, API-клиент в `frontend/src/api/client.js`.
- Auth state — React context (`frontend/src/auth/AuthContext.jsx`).
- Состояния UI: loading / error / empty.

## Git

- Коммиты на английском языке, один логический этап — один коммит.
- После этапа: тесты, `git diff`, проверка отсутствия секретов, commit.

## Agent rules (зафиксированы по реальным ошибкам)

- `select_for_update` всегда вызывать внутри `transaction.atomic()` и до проверок
  доступности; порядок блокировок: Book → BookCopy → Reservation → Issue.
- Конкурентные тесты запускать только на MySQL и в `TransactionTestCase`;
  SQLite не поддерживает `SELECT FOR UPDATE` и даёт `database is locked`.
- Не вызывать `to_representation()` вручную у `ListSerializer`: при `many=True`
  он ожидает список, а не один объект; сериализовать каждый объект отдельно
  или использовать `Serializer(instance, many=True).data`.
- Один маршрут на путь: в `urls.py` не создавать дублирующих записей; список
  пользователей живёт только на `/api/users/`, поиск читателей — на
  `/api/readers/search/`, старый `/api/readers/` удалён.
