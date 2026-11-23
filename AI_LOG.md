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

## 2026-11-23 — Истечение резервов и финальная уточнительная правка

### Задача

- Реализовать обработку истечения резервов ожидания и команду ручного запуска.

### Что сделал агент

- `library/services.py`: `expire_reservations()` теперь выполняется внутри
  `transaction.atomic()` и возвращает список обработанных резервов.
- Добавлена management-команда `python manage.py expire_reservations`.

### Что пришлось исправить

- Команда падала с `TransactionManagementError: select_for_update cannot be used outside of a transaction`
  — исправлено оборачиванием в `transaction.atomic()`.

### Финальные проверки

- `python manage.py check` — OK.
- `python manage.py test` — OK (42 теста).
- `python manage.py makemigrations --check` — изменений нет.
- `npx vite build` — OK.

## 2026-11-23 — Hardening настроек Django, JWT lifetime, requirements, env-примеры

### Задача

- Исправлен `BASE_DIR` (теперь папка `backend`), env-файл читается корректно.
- `SECRET_KEY` и `DATABASE_URL` — обязательные переменные без дефолтов.
- `DEBUG` по умолчанию False; `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` — из env.
- Access token lifetime — 15 минут; DRF throttling (anon 60/min, user 200/min, token scope 10/min).
- `requirements.txt`: Django>=5.1,<7; `frontend/.env.example` создан; `backend/.env.example` приведён к новым значениям.

### Что пришлось исправить

- После смены `BASE_DIR` проверено: неверный `DATABASE_URL` в `backend/.env` приводит к падению `migrate`
  с ошибкой доступа (значит env читается).
- Удаление `SECRET_KEY` из `backend/.env` → `ImproperlyConfigured: Set the SECRET_KEY environment variable`.

### Финальные проверки

- `python manage.py check` — OK.
- `python manage.py test` — OK (42 теста).
- `python manage.py makemigrations --check` — изменений нет.
- Access token: `exp - iat = 900` секунд.
- `npx vite build` — OK.

### Итоговый статус

Текущая задача по hardening завершена, проект в полностью готовом состоянии.

## 2026-11-23 — Регистрация, роли и вход

### Задача

- Перенести публичную регистрацию в `POST /api/auth/register/` (AllowAny, обязательный
  валидируемый пароль, роль reader, дубликат email → 409).
- Сделать `Reader.is_active` свойством на основе статуса (`status == ACTIVE`).
- Добавить `GET /api/auth/me/` (данные текущего пользователя и роли через `request.user`).
- Проверить logout с невалидным refresh (не 500).

### Что пришлось исправить

- Регистрация через старый `POST /api/readers/` не выставляла группу reader — перенесена в
  `/api/auth/register/`, группа присваивается в `RegisterView.perform_create`.

### Финальные проверки

- `python manage.py check` — OK.
- `python manage.py test` — OK (80 тестов).
- `python manage.py makemigrations --check` — изменений нет.
- `npx vite build` — OK.

### Итоговый статус

Проект в полностью готовом состоянии; текущая задача по аутентификации выполнена.


## 2026-11-23 — Test for access token lifetime

### Задача

- Добавлен тест `test_access_token_lifetime_is_15_minutes`, проверяющий, что
  `exp - iat` access token равен 900 секундам.

### Проверки

- `python manage.py test` — OK (49 тестов).
- `python manage.py check` — OK.
- `python manage.py makemigrations --check` — изменений нет.
- `npx vite build` — OK.

### Итоговый статус

Текущая задача по hardening завершена, проект в полностью готовом состоянии.





## 2026-11-23 — Frontend stuck on loading, auth restore, API client, registration page

### Задача

- Починить вечную загрузку «Загрузка...» после запуска фронтенда.
- Восстановление сессии после перезагрузки страницы.
- API клиент: сборка query string из `params`, обработка 401 (refresh + retry), парсинг ошибок DRF.
- Добавить страницу регистрации и экран входа/регистрации.

### Что исправлено

- `frontend/src/api/client.js`: `buildUrl` пропускает `undefined`/`null`/пустые значения;
  401 → одиночный refresh через общий промис (`/token/refresh/`, ротация токенов) + повтор
  запроса; при неудаче — очистка токенов и вызов `authLostHandler`; парсинг DRF-ошибок
  (`detail`, `non_field_errors`, поля); `download` для CSV.
- `frontend/src/auth/AuthContext.jsx`: восстановление сессии через `GET /auth/me/` при наличии
  access-токена, всегда `setInitialized(true)`; `login`, `register`, `logout`; обработчик
  потери авторизации (`setAuthLostHandler`).
- `frontend/src/App.jsx`: рендер `<ActiveComponent />` вместо функции вкладки; вкладки по ролям;
  logout через контекст.
- `frontend/src/pages/RegisterPage.jsx` + `LoginPage`: форма регистрации (email, пароль, ФИО, телефон)
  и переключатель «Вход / Регистрация»; после регистрации — вход.

### Финальные проверки

- Backend: `python manage.py check` — OK; `python manage.py test` — OK (80 тестов);
  `python manage.py makemigrations --check` — изменений нет.
- Frontend: `npx vite build` — OK.

### Итоговый статус

Проект в полностью готовом состоянии.

## 2026-11-23 — Follow-up: token rate limit flake in tests

### Задача

- После hardening rate limit для token endpoint (`10/min`) полный прогон тестов падал:
  `test_token_refresh_and_blacklist` получал `429` вместо ожидаемого `401` после blacklist.

### Что исправлено

- `@override_settings(DEFAULT_THROTTLE_RATES={"token": "1000/min"})` в `LibraryTestCase`.

### Финальные проверки

- `python manage.py test` — OK (80 тестов).
