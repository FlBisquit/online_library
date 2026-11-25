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

## 2026-11-23 — Очередь и бронирование

### Задача

- Исправить 500 при `GET /api/books/id/queue/` (ListSerializer.to_representation) и утечку
  чужих данных: читатель видит только свою позицию и total, сотрудник — весь список.
- `POST /api/books/9999/queue/` → 404 вместо IntegrityError/500.
- Сериализовать параллельный join_queue: 1×201 и 9×409.
- Заменить unique(reader, book, status) на `active_slot` (1 для PENDING/ACTIVE, NULL иначе)
  + data migration; добавить `Reservation.copy` и освобождать именно её.
- Запретить очередь при наличии свободного экземпляра (409).
- Единый порядок блокировок: Book → BookCopy → Reservation → Issue.
- Глобальный обработчик IntegrityError → 409.

### Что исправлено

- `models.py` + миграция `0005_reservation_active_slot_and_copy`: новое поле `copy`,
  `active_slot`, unique-констрейнт, data migration для существующих строк.
- `config/exceptions.py`: `api_exception_handler`, подключён в `REST_FRAMEWORK`.
- `services.py`: все операции в `transaction.atomic()` с одинаковым порядком блокировок;
  проверки после блокировки; active_slot и резервирование конкретного экземпляра.
- `views.py`: безопасный вывод очереди и position/total, проверка существования книги (404).

### Финальные проверки

- `python manage.py check` — OK.
- `python manage.py makemigrations --check` — изменений нет.
- `python manage.py test` — OK (97 тестов, MySQL).
- `npx vite build` — OK.

### Итоговый статус

Проект в полностью готовом состоянии.

## 2026-11-23 — Истечение резервов

### Задача

- `expire_reservations()` был мёртвым кодом: `select_for_update` вне транзакции
  (TransactionManagementError), просроченный резерв вечно держал экземпляр RESERVED.
- `issue_copy` не проверял `expires_at` у ACTIVE-резерва; `_promote_next` обрабатывал
  максимум один просроченный резерв и не продвигал очередь дальше.
- Нужны системные записи ActionLog и ленивый вызов истечения из пользовательских сценариев.

### Что исправлено

- `ActionLog.user` -> nullable `SET_NULL`, миграция
  `0006_actionlog_nullable_user`; системные действия пишутся с `user=None`.
- `services.expire_reservations(book_id=None)`: одна транзакция, порядок блокировок
  Book -> BookCopy -> Reservation, цикл до полной обработки просроченных резервов.
  Каждый резерв -> EXPIRED + `active_slot=NULL`, экземпляр освобождается и сразу
  передаётся следующему PENDING через `_promote_next`; пишется
  `ActionLog(action="reservation.expire", user=None, details=...)`.
- `_promote_next` больше не ищет просроченные резервы сам — все изменения
  инициирует внешний цикл, поэтому логируется каждый резерв в цепочке.
- Ленивый вызов `expire_reservations`: `join_queue`, `issue_copy`, `return_issue`,
  `cancel_reservation`, карточка книги и список экземпляров (GET).
- `issue_copy`: ACTIVE-резерв читателя с истёкшим `expires_at` -> 409, выдача
  запрещена (резерв при этом истекает и очередь продвигается).
- Management command `expire_reservations` для cron: опциональный `--book-id`,
  вывод количества обработанных резервов.
- Тесты с подменой времени через `patch("django.utils.timezone.now")`: продвижение
  следующего в очереди, цепочка из 3 резервов за один вызов, выдача по просроченному
  резерву -> 409, идемпотентность повторного вызова, ленивое истечение из views.

### Финальные проверки

- `python manage.py check` — OK.
- `python manage.py makemigrations --check` — изменений нет.
- `python manage.py test` — OK (111 тестов, MySQL).
- `python manage.py expire_reservations` — OK (0 обработано).
- `npx vite build` — не требуется (frontend не менялся).

### Итоговый статус

Истечение резервов работает лениво и через cron; просроченные брони больше не блокируют экземпляры.

## 2026-11-23 — Единая карта переходов статусов

### Задача

- Заменить разбросанные проверки статусов единой картой переходов.
- Реализовать OVERDUE и LOST, запретить self-service возврат.
- Хранить в ActionLog старый и новый статус, логировать все изменения, включая
  FULFILLED и EXPIRED.

### Что исправлено

- Новый `library/transitions.py`: карты `ISSUE_TRANSITIONS`, `RESERVATION_TRANSITIONS`,
  `BOOK_COPY_TRANSITIONS` и функция `change_status(obj, new_status, user, **extra)`.
  Недопустимый переход -> `Conflict` (409) «Переход из X в Y нельзя». Изменение
  объекта и запись ActionLog происходят в одной транзакции.
- `ActionLog`: поля `entity_type`, `entity_id`, `old_status`, `new_status` и индексы
  `(entity_type, entity_id)` и `created_at`; миграция `0007_actionlog_status_transition`.
- `services.py`: все смены статусов идут только через `change_status`, включая
  FULFILLED (выдача), EXPIRED (истечение), RESERVED (продвижение очереди).
  Добавлены `mark_overdue()` (UPDATE просроченных ISSUED -> OVERDUE) и
  `mark_issue_lost()` (выдача и экземпляр -> LOST). Возврат разрешён для
  ISSUED, OVERDUE и LOST.
- Права: `IssueReturnView` и новый `IssueMarkLostView` — `IsLibrarianOrAdmin`;
  читатель может отменить только свою бронь, сотрудник — любую.
- Новый эндпоинт `POST /api/issues/<id>/mark-lost/`; ленивый `mark_overdue()` при
  выдаче списков выдач; management command `manage.py mark_overdue` для cron.
- `BookCopySerializer` запрещает вручную выставлять ISSUED и RESERVED.

### Финальные проверки

- `python manage.py check` — OK.
- `python manage.py makemigrations --check` — изменений нет.
- `python manage.py test` — OK (130 тестов, MySQL), включая параметризованную
  матрицу всех пар статусов для Issue/Reservation/BookCopy, проверку отката
  статуса и журнала при исключении, права 403, mark_overdue и mark-lost.
- `python manage.py mark_overdue` — OK (0 обработано).
- `npx vite build` — не требуется (frontend не менялся).

### Итоговый статус

Переходы статусов централизованы, просрочки и утеря обрабатываются, журнал содержит
полную историю изменений с old_status/new_status.

## 2026-11-23 — Журнал действий (API и экран)

### Задача

- Модель `ActionLog` уже велась, но не было ни одного эндпоинта и экрана.
- В `docs/PLAN.md` пункт «журнал действий» был ошибочно отмечен выполненным.
- Требование задания: показывать «кто, когда и какой статус изменил».

### Что сделано

- `GET /api/action-log/`: только `IsLibrarianOrAdmin` (читатель получает 403),
  `PageNumberPagination` (20 записей), сортировка `-created_at, -id`.
- Фильтры `user`, `entity_type`, `entity_id`, `action`, `date_from`, `date_to`.
  Даты разбираются через `date.fromisoformat`, целочисленные параметры через
  `int()`; некорректные значения дают 400.
- `ActionLogSerializer`: `id`, `user {id, full_name, email}` (или `null`
  для системных записей), `action`, `entity_type`, `entity_id`, `old_status`,
  `new_status`, `created_at`, `details`. Запрос использует `select_related("user")`.
- `assertNumQueries(3)` подтверждает отсутствие N+1: проверка роли + COUNT +
  SELECT с JOIN пользователя, независимо от числа строк.
- Тесты: 403 для читателя, пагинация и порядок, все фильтры, невалидные
  параметры, формат сериализатора, системная запись с `user=None`, а также
  корректные `old_status`/`new_status` после `issue_copy`, `return_issue`
  и `cancel_reservation`.
- Фронтенд: новый `ActionLogPage` с фильтрами, таблицей, пагинацией и
  состояниями loading / empty / error; русские подписи действий, статусов
  и типов объектов. Вкладка «Журнал» добавлена в админку и в панель
  библиотекаря (с пометкой «Только для чтения»).
- `docs/PLAN.md`: исправлена ложная отметка, обновлены счётчик тестов
  (145) и описание фронтенда.

### Финальные проверки

- `python manage.py check` — OK.
- `python manage.py makemigrations --check --dry-run` — изменений нет.
- `python manage.py test` — OK (145 тестов, MySQL).
- `npx vite build` — OK (frontend изменён).

### Итоговый статус

Журнал действий доступен через API и в интерфейсе: сотрудники видят кто, когда
и какой статус изменил, с фильтрами и постраничным просмотром.

## 2026-11-23 — Отчёт по книгам (переписан)

### Задача

- Заменить старые отчёты на отчёт «загрузка объектов и число отмен за период»;
  для библиотеки объект — книга.
- Старые `/reports/issues/`, `/reports/cancellations/` и
  `/reports/issues/export/` не подходили: не было периода и названий книг,
  отмены считались по `queue_date`, даты ломали запрос 500, CSV был дампом
  выдач, книги без выдач терялись, интерфейса не было.

### Что сделано

- `Reservation.cancelled_at` (nullable, индекс `(book, cancelled_at)`);
  `Issue(issued_at)` тоже проиндексировано. Миграции
  `0008_reservation_cancelled_at_issue_issue_issued_at_idx_and_more` и
  `0009_backfill_reservation_cancelled_at`: для старых отменённых броней
  момент отмены заполнен из `queue_date` как единственной доступной отметки.
- `change_status()` проставляет `cancelled_at = timezone.now()` только при
  переходе Reservation в `CANCELLED`; остальные переходы оставляют поле пустым.
- Логика вынесена в `library/services/reports.py` (существующий `services.py`
  преобразован в пакет `services/__init__.py`). `books_report()` делает
  **один SQL-запрос** от `Book` с `Count(..., filter=Q(...), distinct=True)`:
  условия периода находятся внутри агрегатов, поэтому книги без выдач
  остаются с нулями, а декартово умножение двух связанных таблиц не искажает
  счётчики.
- `GET /api/reports/books/`: `IsLibrarianOrAdmin`, обязательные
  `date_from`/`date_to` в формате `YYYY-MM-DD`, неверные даты и
  `date_from > date_to` дают 400. Период полуоткрытый
  `[date_from, date_to + 1 день)` в UTC. Ответ: `book_id`, `title`,
  `loans`, `overdue`, `cancellations`. `assertNumQueries(2)`:
  проверка роли + один запрос с агрегацией.
- `GET /api/reports/books/export/`: тот же набор строк, CSV в `utf-8-sig`
  (BOM для Excel), русские заголовки `ID, Книга, Выдачи, Просрочено, Отмены`,
  имя `report_<from>_<to>.csv`; значения начинающиеся с `= + - @`,
  экранируются апострофом. Старые три эндпоинта удалены — теперь 404.
- Тесты: книга без выдач с нулями, границы 31.10 23:59 / 01.11 00:00 /
  30.11 23:59:59 / 01.12 00:00, фильтрация отмен именно по `cancelled_at`,
  невалидные даты, 403 для читателя, константное число SQL-запросов,
  CSV совпадает с JSON, BOM и защита от инъекций.
- Фронтенд: вкладка «Отчёт» в админке; период по умолчанию — последние
  30 дней, таблица, состояния loading / empty / error и кнопка
  «Скачать CSV» через `apiClient.download` (токен добавляется клиентом).
- `docs/PLAN.md`: обновлены счётчик тестов (163) и описание API/фронтенда.

### Финальные проверки

- `python manage.py check` — OK.
- `python manage.py makemigrations --check --dry-run` — изменений нет.
- `python manage.py test` — OK (163 теста, MySQL).
- `npx vite build` — OK (frontend изменён).

### Итоговый статус

Отчёт по книгам считается базой данных одним запросом, показывает выдачи,
просрочки и отмены за выбранный период, выгружается в Excel-совместимый CSV
и доступен администратору через интерфейс.

## 2026-11-23 — Управление каталогом и пользователями

### Задача

- Исправить 405 на `GET /api/readers/` и развести админские экраны.
- Дать администратору те же права на каталог, что и библиотекарю;
  управление пользователями оставить только администратору.
- Добавить CRUD книг, экземпляров, авторов и жанров, управление ролями
  и статусами пользователей и новый AdminPage с вкладками.

### Что сделано

- Добавлен `IsCatalogEditor` (наследник `IsLibrarianOrAdmin`) и
  `CatalogPagination` с параметром `limit` (максимум 100). Чтение каталога
  осталось публичным, запись — только сотрудникам.
- Книги: `PATCH/PUT/DELETE /api/books/<id>/`. Удаление через
  `services/catalog.py` блокируется с 409, если есть выдачи или живые
  бронирования (`PENDING`/`ACTIVE`); блокировки идут Book → BookCopy → Reservation.
- Экземпляры: `GET/PATCH/DELETE /api/copies/<id>/`. Статус меняется только
  через `change_status` (карта переходов, ActionLog); `ISSUED`/`RESERVED`
  вручную запрещены. Удаление с выдачами даёт 409.
- Справочники: CRUD `/api/authors/<id>/` и `/api/genres/<id>/` с поиском
  и пагинацией.
- Пользователи: дублирующий `readers/` убран, добавлены
  `GET/POST /api/users/` и `GET/PATCH /api/users/<id>/` (только `IsAdmin`).
  POST создаёт библиотекаря или админа с явной ролью. GET ищет по email/ФИО,
  фильтрует по `role`/`status` и пагинируется.
- `services/users.py`: замена группы в одной транзакции, статусы только
  `ACTIVE`/`BLOCKED`, запрет понизить/заблокировать себя и последнего
  администратора (409). Каждое изменение роли/статуса и создание пишутся
  в `ActionLog` с `user=request.user`.
- Фронтенд: AdminPage разбит на вкладки «Книги», «Пользователи», «Журнал»,
  «Отчёт». Новые `BooksAdminPage` и `UsersAdminPage`: таблицы с поиском,
  фильтрами и пагинацией, формы с multi-select авторов/жанров из справочников,
  подтверждение удаления, ошибки по полям, loading/empty/error. API-клиент
  теперь сохраняет структурированные данные ошибки.
- `docs/PLAN.md`: обновлены счётчик тестов (195) и описание новых экранов.

### Финальные проверки

- `python manage.py check` — OK.
- `python manage.py makemigrations --check --dry-run` — изменений нет.
- `python manage.py test` — OK (195 тестов, MySQL); один полный прогон дал
  транзиентный сбой, два последующих и повтор concurrency-тестов — зелёные.
- `npx vite build` — OK (frontend изменён).

### Итоговый статус

Каталог и пользователи управляются из админки с соблюдением ролей;
недопустимые удаления и изменения прав возвращают 409, а изменения
ролей и статусов фиксируются в журнале.

## 2026-11-23 — Исправления по итогам аудита

### Задача

Проверить уже сданный функционал и устранить найденные проблемы: регистрацию
на чистой БД, рассинхронизацию статуса экземпляра при ручном возврате,
удаление экземпляра с живой бронью, порядок блокировок и устаревшую документацию.

### Что сделано

- `RegisterView` использует `Group.objects.get_or_create` для роли `reader` —
  регистрация больше не падает, если демо-данные не загружались.
- `services/catalog.py` запрещает ручной перевод `ISSUED`/`RESERVED` в
  `AVAILABLE` (409): освобождение экземпляра остаётся за сервисами возврата
  и истечения брони. В админке недоступные варианты статуса отключены.
- `delete_copy` дополнительно проверяет живые бронирования `PENDING`/`ACTIVE`
  под блокировкой (Book → BookCopy → Reservation) и возвращает 409.
- `return_issue` блокирует следующую бронь до блокировки выдачи;
  `_promote_next` принимает уже заблокированную бронь. Порядок блокировок
  Book → BookCopy → Reservation → Issue теперь соблюдается и подтверждён
  тестом по SQL `FOR UPDATE`.
- Обновлены `docs/API_DESIGN.md`, `docs/SPEC.md`, `docs/TEST_PLAN.md`:
  registry через `/api/auth/register/`, новые эндпоинты каталога/пользователей,
  журнал и отчёты. Удалены неиспользуемые `BookAuthorSerializer`,
  `BookGenreSerializer`, `IsReader`, `IsLibrarian`, `IsReaderOrLibrarian`.
- Каждое исправление сначала покрыто красным тестом и закоммичено отдельно.

### Финальные проверки

- `python manage.py check` — OK.
- `python manage.py makemigrations --check --dry-run` — изменений нет.
- `python manage.py test` — OK (199 тестов, MySQL).
- `npx vite build` — OK (frontend изменён в части статусов экземпляров).

### Итоговый статус

Аудит закрыт: известные проблемы устранены, документация соответствует
реализации, рабочее дерево чистое кроме изначально незаверсионированного
`proj.zip`.

## 2026-11-25 — Кабинет читателя и панель библиотекаря

### Задача

- Вывести «Мои выдачи» и «Панель библиотекаря» из состояния id-only.
- Добавить backend-контракт для текущих выдач, броней, очередей и отчётов.
- Реализовать frontend-экраны с loading / empty / error, i18n и ручным сценарием.

### Что сделано

- `IssueSerializer`: вложенные read-only `book {id, title}`, `reader {id, full_name}`,
  `copy {inventory_number}`.
- `ReservationSerializer`: вложенные `book`, `reader`, `copy`, `position`, `total`,
  `expires_at`.
- `GET /api/auth/me/reservations/` — брони и очереди текущего читателя.
- `GET /api/issues/?due=today|overdue&search=...` — выдачи сотрудника.
- `GET /api/reservations/?status=ACTIVE` — ожидания выдачи.
- `MyLoansPage`: «Сейчас на руках», «Мои очереди и брони», «История» с пагинацией.
- `LibrarianPage`: форма выдачи, списки ожиданий/выдач, действия возврата и потери.
- `frontend/src/i18n.js`: даты через `Intl.DateTimeFormat("ru-RU")` и русские статусы.
- `README.md`: ручной сценарий.

### Финальные проверки

- `python manage.py check` — OK.
- `python manage.py makemigrations --check --dry-run` — изменений нет.
- `python manage.py test` — OK (203 теста, MySQL).
- `npx vite build` — OK (frontend изменён).

### Итоговый статус

Кабинет читателя и панель библиотекаря переведены на человекочитаемые данные,
фильтры и действия библиотекаря реализованы, ручной сценарий задокументирован.
