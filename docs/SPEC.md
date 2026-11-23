# Спецификация проекта — Информационная система библиотеки

## 1. Цель

Онлайн-библиотека для управления каталогом книг, физическими экземплярами,
выдачами читателей, очередью ожидания и журналом действий.

## 2. Стек

- Frontend: React (Vite).
- Backend: Django + Django REST Framework.
- База данных: MySQL / MariaDB.
- Авторизация: JWT (djangorestframework-simplejwt, refresh token blacklist).
- AI-агент: Aider.

## 3. Основные сущности

- `books` — каталог книг (ISBN уникален).
- `book_copies` — физические экземпляры книг (статус `AVAILABLE` / `ISSUED` / `RESERVED` / `LOST` / `RETIRED`).
- `readers` — пользователи библиотеки (email + роли).
- `issues` — выдачи книг (статусы `ISSUED` / `RETURNED` / `OVERDUE` / `LOST`).
- `reservations` — очередь ожидания / бронирования (`PENDING` / `ACTIVE` / `FULFILLED` / `CANCELLED` / `EXPIRED`).
- `action_logs` — журнал действий пользователей.
- `authors`, `genres`, `book_authors`, `book_genres` — справочные сущности.

Минимум: 6 связанных таблиц (без учёта справочных) — фактически система использует больше.

## 4. Роли

- Читатель (`reader`).
- Библиотекарь (`librarian`).
- Администратор (`admin`).

## 5. Ключевые бизнес-правила

1. Один экземпляр книги выдаётся одному читателю одновременно.
2. Стандартный срок выдачи: 14 дней (`LOAN_PERIOD`).
3. Срок резерва в очереди: 48 часов (`RESERVATION_PERIOD`).
4. Выдача и изменение статуса экземпляра выполняются в одной транзакции
   (`transaction.atomic` + `select_for_update`).
5. Допустимые переходы статусов выдач и бронирований — централизованно.

## 6. API-разделы

- `POST /api/token/` — получение пары JWT.
- `POST /api/token/refresh/` — обновление access token.
- `POST /api/token/blacklist/` — отзыв refresh token.
- `GET /api/books/`, `GET /api/books/{id}/` — каталог (поиск, фильтры, пагинация).
- `POST /api/books/`, `PATCH/PUT/DELETE /api/books/{id}/`, `GET /api/books/{book_id}/copies/`, `POST /api/books/{book_id}/copies/`, `PATCH/DELETE /api/copies/{id}/` — каталог.
- `GET/POST /api/authors/`, `GET/POST /api/genres/` и CRUD `/api/authors/{id}/`, `/api/genres/{id}/` — справочники.
- `POST /api/auth/register/` — публичная регистрация читателя.
- `GET/POST /api/users/`, `GET/PATCH /api/users/{id}/` — управление пользователями (только администратор).
- `GET /api/readers/{id}/`, `GET /api/readers/{id}/issues/` — читатели и история.
- `GET /api/issues/`, `POST /api/issues/`, `POST /api/issues/{id}/return/` — выдачи.
- `GET /api/books/{book_id}/queue/`, `POST /api/books/{book_id}/queue/`, `GET /api/books/{book_id}/queue/{reader_id}/position/` — очередь.
- `GET /api/reservations/{id}/`, `POST /api/reservations/{id}/cancel/` — бронирования.
- `GET /api/action-log/` — журнал действий.
- `GET /api/reports/books/`, `GET /api/reports/books/export/` — отчёты.

Полная спецификация API: `docs/API_DESIGN.md`.
