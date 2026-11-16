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
