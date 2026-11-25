# Спецификация проекта — Информационная система библиотеки

> **Происхождение документа (важно).** Файл создан коммитом `b8970d8`
> 2026-11-16 12:24:26 +05:00 — **после** того, как основные модели, API и тесты
> были реализованы коммитами `9238407` … `c71288a` в 11:48–12:10 того же дня.
> Как «спецификация, написанная до кода», этот файл не использовался и не может
> считаться таковой: он описывает фактически построенную систему. Документы,
> действительно созданные до кода (2026-11-09, коммит `b5876b3` и последующие):
> `docs/BUSINESS_LOGIC.md`, `docs/DATABASE_DESIGN.md`, `docs/API_DESIGN.md`,
> `docs/BOOK_QUEUE_DESIGN.md`, `docs/TEST_PLAN.md`. Ниже даты и статусы не
> переписаны задним числом.

## 1. Цель

Онлайн-библиотека для управления каталогом книг, физическими экземплярами,
выдачами читателей, очередью ожидания и журналом действий.

## 2. Стек

- Frontend: React (Vite).
- Backend: Django + Django REST Framework.
- База данных: MySQL / MariaDB (тесты и демонстрация — MySQL).
- Авторизация: JWT (djangorestframework-simplejwt, refresh token blacklist).
- AI-агент: Aider (конфигурация `.aider.conf.yml`, `.aiderignore`).

## 3. Основные сущности

- `books` — каталог книг (ISBN уникален, есть `cover_url`).
- `book_copies` — физические экземпляры (`AVAILABLE` / `ISSUED` / `RESERVED` /
  `LOST` / `RETIRED`).
- `readers` — пользователи библиотеки (email + роли через группы).
- `issues` — выдачи (`ISSUED` / `RETURNED` / `OVERDUE` / `LOST`).
- `reservations` — очередь/бронирования (`PENDING` / `ACTIVE` / `FULFILLED` /
  `CANCELLED` / `EXPIRED`), поля `copy`, `active_slot`, `cancelled_at`, `expires_at`.
- `action_logs` — журнал действий, включая системные записи (`user=None`) и
  `old_status`/`new_status`.
- `authors`, `genres`, `book_authors`, `book_genres` — справочные сущности.

Минимум 6 связанных таблиц (без учёта справочных) — фактически система использует больше.

## 4. Роли

- Читатель (`reader`) — группа `reader` назначается при регистрации через
  `Group.objects.get_or_create`.
- Библиотекарь (`librarian`).
- Администратор (`admin`).

Проверки прав — в `library/permissions.py`; роли в JWT не дублируются,
`Reader.has_role()` читает их из БД, поэтому смена роли применяется сразу.

## 5. Ключевые бизнес-правила

1. Один экземпляр книги выдаётся одному читателю одновременно.
2. Стандартный срок выдачи: 14 дней (`LOAN_PERIOD`).
3. Срок резерва в очереди: 48 часов (`RESERVATION_PERIOD`).
4. Выдача, возврат и изменение статуса экземпляра выполняются в одной
   транзакции (`transaction.atomic` + `select_for_update`); порядок блокировок
   Book → BookCopy → Reservation → Issue.
5. Допустимые переходы статусов выдач, броней и экземпляров заданы централизованной
   картой (`change_status()`), недопустимые дают 409.
6. Конкурентные проверки — только на MySQL; SQLite не поддерживает
   `SELECT FOR UPDATE` (правило зафиксировано в `CONVENTIONS.md`).
7. Любая правка схемы — через миграцию; перед коммитом
   `makemigrations --check --dry-run`.

## 6. API-разделы (фактически реализованные маршруты)

Базовый префикс: `/api/`. Полный контракт — `docs/API_DESIGN.md`.

- **JWT:** `POST /api/token/`, `POST /api/token/refresh/`,
  `POST /api/token/blacklist/`.
- **Регистрация и профиль:** `POST /api/auth/register/`,
  `GET /api/auth/me/`, `GET /api/auth/me/reservations/`.
- **Каталог:** `GET/POST /api/books/`, `GET/PATCH/PUT/DELETE /api/books/<id>/`,
  `GET/POST /api/books/<book_id>/copies/`,
  `GET/PATCH/PUT/DELETE /api/copies/<id>/`, CRUD `/api/authors/`,
  `/api/authors/<id>/`, `/api/genres/`, `/api/genres/<id>/`. Чтение публичное,
  запись — `IsCatalogEditor`; списание в `RETIRED` запрещено при открытой выдаче
  или живой брони.
- **Очередь:** `GET/POST /api/books/<book_id>/queue/`,
  `GET /api/books/<book_id>/queue/<reader_id>/position/`.
- **Пользователи:** `GET/POST /api/users/`, `GET/PATCH/PUT /api/users/<id>/`
  (только администратор; PUT требует полного набора `role` и `status`);
  `GET /api/readers/<id>/`, `GET /api/readers/<id>/issues/` (сам пользователь
  или сотрудники), `GET /api/readers/search/` (сотрудники).
- **Выдачи:** `GET/POST /api/issues/` (список — только сотрудники),
  `POST /api/issues/<id>/return/`, `POST /api/issues/<id>/mark-lost/`.
- **Бронирования:** `GET /api/reservations/` (только сотрудники, фильтр
  `status`), `GET /api/auth/me/reservations/` (свои брони),
  `GET /api/reservations/<id>/`, `POST /api/reservations/<id>/cancel/`
  (владелец или сотрудники).
- **Журнал:** `GET /api/action-log/` — только сотрудники, фильтры и пагинация.
- **Отчёты:** `GET /api/reports/books/`, `GET /api/reports/books/export/`
  (CSV в UTF-8 с BOM) — только сотрудники.

Историческое расхождение: ранний `docs/API_DESIGN.md` описывал публичную
регистрацию на `POST /api/readers/`; рабочая схема — `/api/auth/register/`,
старый маршрут `/api/readers/` удалён как дублирующий.

## 7. Фактическое состояние и расхождения

- Реализовано: модели, миграции, перечисленные эндпоинты, React-экраны,
  демо-загрузка, 136 уникальных тестов, скрипт проверки гонки выдачи.
- Журнал действий изначально был ошибочно отмечен выполненным в плане; API и
  экран добавлены 2026-11-23 (`docs/AI_LOG.md`, запись 10).
- Исправления сессии 20 (реальные коммиты): `c4c365e` — покрытие всех коммитов
  в логах; `cfca710` — 23 красных регрессионных теста; `2dfb338` — брони,
  списание и продвижение очереди; `09f0b18` — валидация, throttle, CSV, отчёты
  и демо-данные; `8610ca6` — фронтенд. Все 136 тестов зелёные.
- Открытые вопросы безопасности (не отмечены как реализованные):
  слабый плейсхолдер `SECRET_KEY` в `.env.example`, `DEBUG=True` в локальном
  `.env`, отдельные throttle scope для refresh/blacklist/register, `::1` вместо
  `[::1]`, TLS/HSTS и политика показа `total` в очередях. Подробности —
  `docs/AI_REVIEW.md`, `docs/PLAN.md`.
- Текущая спецификация не фиксирует нереализованные функции как сделанные;
  статус каждого пункта сверяется с планом и журналом AI-агента.
