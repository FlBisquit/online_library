# AI_LOG — журнал AI-агента и значимых задач проекта

## 2026-11-16 — Аудит и начало реализации онлайн-библиотеки

### Задача

Выполнить аудит проекта онлайн-библиотеки в соответствии с требованиями
AI Driven Development и приступить к доведению проекта до рабочего состояния.

### Известное состояние на момент аудита

- Реализованы модели БД (`library`): Author, Genre, Book, BookAuthor, BookGenre,
  BookCopy, Reader, Issue, Reservation.
- Реализованы документы проектирования: `docs/DATABASE_DESIGN.md`,
  `docs/BUSINESS_LOGIC.md`, `docs/API_DESIGN.md`, `docs/BOOK_QUEUE_DESIGN.md`,
  `docs/TEST_PLAN.md`.
- Отсутствовали: миграции, сериализаторы, views, tests, auth, журнал действий,
  отчёты, фронтенд-экраны, demo-данные.

### Выполненные этапы

1. `Configure Django settings for MySQL and JWT authentication` — MySQL,
   SimpleJWT, TokenBlacklist, env (`django-environ`), `.env.example`.
2. `Implement reader user model with roles and permissions` — кастомный Reader
   как Django-пользователь, группы `reader` / `librarian` / `admin`.
3. `Add JWT token endpoints and admin registration`.
4. `Implement library serializers for catalog, issues and reservations`.
5. `Implement library API views for catalog issues and queue` — транзакции,
   `select_for_update`, отчёты, журнал действий.
6. `Add backend test suite with concurrency coverage` — 42 теста, включая
   конкурентную выдачу двух читателей за один экземпляр.
7. `Implement action journal for library operations`.
8. `Add demo data loading command for library`.
9. `Build React frontend screens for library`.

### Обнаруженные ошибки и исправления

- Дублирование определения модели `Reader` в процессе рефакторинга — исправлено.
- Неверный импорт `Conflict` из `rest_framework.exceptions` — заменён на кастомный
  исключение в `library.services`.
- `get_permissions()` возвращал классы вместо экземпляров — исправлено.
- Таблицы `token_blacklist` ссылались на `auth_user` (миграрации применились до смены
  `AUTH_USER_MODEL`) — таблицы пересозданы, FK указывает на `library_reader`.
- `IsAuthenticated`/`AllowAny` в `permission_classes` — исправлено на экземпляры.

### Результаты проверок

- `python manage.py check` — без ошибок.
- `python manage.py migrate` — применены миграции к MySQL.
- `python manage.py test` — 42 теста, все проходят.
- `npx vite build` — сборка фронтенда успешна.

## 2026-11-16 — Продолжение: отчёты, журнал, демо-данные, фронтенд

### Задача

- Добавлены endpoints отчётов: агрегация выдач по книгам, отмена бронирований за период, CSV-экспорт.
- Журнал действий (`ActionLog`) записывается в транзакциях выдачи/возврата/отмены/в очереди.
- Команда `load_demo_data` (24 книги, 48 экземпляров, 48 выдач, 8 читателей).
- React-фронтенд: вход, каталог, мои выдачи, панель библиотекаря, админка.

### Замечания

- `POST /api/readers/` реализован как публичная регистрация (в `docs/API_DESIGN.md`
  фиксировалось `IsAuthenticated` — отклонено в пользу рабочей схемы регистрации).
- Выдача доступных экземпляров разрешена библиотекарю и администратору
  (персональный читатель не может выдавать книги).

## 2026-11-16 — Финальное состояние проекта

### Выполненные работы

- Полный аудит и доведение онлайн-библиотеки до рабочего состояния.
- Backend: MySQL, JWT (SimpleJWT + blacklist), модели, миграции, API (каталог, выдача, возврат,
  очередь, резервы, отчёты, журнал), 42 теста (включая race-тест), demo data (`load_demo_data`).
- Frontend: React (Vite) — вход, каталог, мои выдачи, панель библиотекаря, админка, выход.

### Финальные проверки

- `python manage.py check` — без ошибок.
- `python manage.py test` — 42 теста, все проходят (MySQL).
- `npx vite build` — сборка фронтенда успешна.

### Итоговый статус

Проект готов к запуску с чистой базой данных MySQL, тестированию и защите преподавателю.

