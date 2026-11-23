# API Design — Информационная система библиотеки

## 1. Общие принципы

- Base URL: `/api/`.
- Формат данных: JSON, Django REST Framework.
- Пагинация: `page` / `limit` (DRF pagination, `limit` до 100).
- Идентификаторы: целые числа (BigAutoField).
- Конфликты бизнес-логики (невозможная выдача, удаление книги с выдачами,
  понижение себя или последнего администратора) возвращают `409 Conflict`.

## 2. Аутентификация и права доступа

- Чтение каталога (`books`, `copies`, `authors`, `genres`) — `AllowAny`.
- Изменение каталога — `IsCatalogEditor` (библиотекарь или администратор).
- Управление пользователями — `IsAdmin`; публичная регистрация — `AllowAny`.
- Личные данные (`auth/me`, история выдач) — `IsAuthenticated`.
- Журнал действий и отчёты — `IsLibrarianOrAdmin`.

Идентификация пользователя всегда берётся из `request.user`, а не из тела запроса.

## 3. Endpoints

### 3.1. Каталог книг

#### GET /api/books/
- **Назначение:** список книг (поиск, фильтры, пагинация).
- **Параметры:** `search`, `author`, `genre`, `publication_year`, `page`, `limit`.
- **Ответ:** `200 OK` — `{"count": <int>, "results": [<book>]}`.
- **Авторизация:** `AllowAny`.

#### GET /api/books/{id}/
- **Назначение:** получение книги.
- **Ответ:** `200 OK`; `404 Not Found`.
- **Авторизация:** `AllowAny`.

#### POST /api/books/
- **Тело:** `{"title": "...", "description": "...", "isbn": "...", "publication_year": 2020, "publisher": "...", "authors": [1, 2], "genres": [1]}`.
- **Ответ:** `201 Created`; ошибки `400`, `409` (ISBN уже существует).
- **Авторизация:** `IsCatalogEditor`.

#### PATCH / PUT / DELETE /api/books/{id}/
- **Назначение:** редактирование и удаление книги.
- **Ответ:** `200 OK` / `204 No Content`; `400`, `403`, `404`, `409`.
- `DELETE` возвращает `409`, если есть выдачи или живые бронирования
  (`PENDING` / `ACTIVE`).
- **Авторизация:** `IsCatalogEditor`.

### 3.2. Физические экземпляры книг

#### GET /api/books/{book_id}/copies/
- **Назначение:** список экземпляров конкретной книги.
- **Ответ:** `200 OK` — paginated список экземпляров.
- **Авторизация:** `AllowAny`.

#### POST /api/books/{book_id}/copies/
- **Тело:** `{"inventory_number": "...", "status": "AVAILABLE"}`.
- **Ответ:** `201 Created`; ошибки `400`, `404`, `409`.
- **Авторизация:** `IsCatalogEditor`.

#### GET /api/copies/{id}/
- **Ответ:** `200 OK`; `404 Not Found`.
- **Авторизация:** `AllowAny`.

#### PATCH / PUT /api/copies/{id}/
- **Тело:** `{"inventory_number": "...", "status": "LOST"}`.
- Статус меняется только по карте переходов; `ISSUED` и `RESERVED` выставляются
  сервисами выдачи/бронирования. Ручной возврат `ISSUED`/`RESERVED` в
  `AVAILABLE` тоже запрещён (`409`).
- **Ответ:** `200 OK`; ошибки `400`, `403`, `404`, `409`.
- **Авторизация:** `IsCatalogEditor`.

#### DELETE /api/copies/{id}/
- `409`, если по экземпляру есть выдачи или живые бронирования.
- **Авторизация:** `IsCatalogEditor`.

### 3.3. Авторы и жанры

- `GET /api/authors/`, `GET /api/genres/` — списки с поиском и пагинацией, `AllowAny`.
- `POST /api/authors/`, `POST /api/genres/` — создание, `IsCatalogEditor`.
- `GET / PATCH / PUT / DELETE /api/authors/{id}/`,
  `GET / PATCH / PUT / DELETE /api/genres/{id}/` — CRUD справочника,
  запись — `IsCatalogEditor`.

### 3.4. Пользователи и регистрация

#### POST /api/auth/register/
- **Назначение:** публичная регистрация читателя.
- **Тело:** `{"full_name": "...", "email": "...", "password": "...", "phone": "..."}`.
- **Ответ:** `201 Created`; ошибки `400`, `409`.
- Группа `reader` создаётся автоматически, если её нет.
- **Авторизация:** `AllowAny`.

#### GET /api/auth/me/
- **Ответ:** данные текущего пользователя и его роли.
- **Авторизация:** `IsAuthenticated`.

#### GET /api/users/
- **Параметры:** `search` (email или ФИО), `role`, `status`, `page`, `limit`.
- **Авторизация:** `IsAdmin`.

#### POST /api/users/
- **Тело:** `{"email": "...", "password": "...", "full_name": "...", "phone": "...", "role": "librarian"}`.
- Допустимые явные роли: `librarian`, `admin`.
- **Ответ:** `201 Created`; ошибки `400`, `403`, `409`.
- **Авторизация:** `IsAdmin`.

#### GET /api/users/{id}/
- **Ответ:** `200 OK`; `404 Not Found`.
- **Авторизация:** `IsAdmin`.

#### PATCH /api/users/{id}/
- **Тело:** `{"role": "reader"}` и/или `{"status": "ACTIVE"|"BLOCKED"}`.
- Нельзя понизить или заблокировать себя и последнего активного администратора (`409`).
- Каждое изменение пишется в `ActionLog`.
- **Авторизация:** `IsAdmin`.

#### GET /api/readers/{id}/ и GET /api/readers/{id}/issues/
- Данные читателя и история его выдач.
- **Авторизация:** `IsAuthenticated`.
- Списочный маршрут `GET /api/readers/` удалён; используется `/api/users/`.

### 3.5. Выдача, возврат и история

- `POST /api/issues/` — выдача экземпляра; `GET /api/issues/` — список выдач.
- `POST /api/issues/{id}/return/` — возврат.
- `POST /api/issues/{id}/mark-lost/` — отметить выдачу утерянной.
- `GET /api/readers/{id}/issues/` — история выдач читателя.
- **Авторизация:** `IsAuthenticated` (изменения выдач — `IsLibrarianOrAdmin`).

### 3.6. Очередь и бронирования

- `GET /api/books/{book_id}/queue/` — очередь на книгу.
- `POST /api/books/{book_id}/queue/` — добавить читателя в очередь.
- `GET /api/books/{book_id}/queue/{reader_id}/position/` — позиция в очереди.
- `GET /api/reservations/{id}/` — состояние брони.
- `POST /api/reservations/{id}/cancel/` — отмена брони.

### 3.7. Журнал и отчёты

- `GET /api/action-log/` — журнал действий с фильтрами и пагинацией.
- `GET /api/reports/books/?date_from=ГГГГ-ММ-ДД&date_to=ГГГГ-ММ-ДД` —
  aggregated-отчёт по выдачам, просрочкам и отменам.
- `GET /api/reports/books/export/` — тот же отчёт CSV (`utf-8-sig`).
- Обе даты обязательны; неверный период — `400`.
- **Авторизация:** `IsLibrarianOrAdmin`.

## 4. Полная таблица API endpoints

| Метод | URL | Раздел | Назначение | Auth |
|---|---|---|---|---|
| POST | /api/token/ | Auth | Пара JWT | AllowAny |
| POST | /api/token/refresh/ | Auth | Обновление access | AllowAny |
| POST | /api/token/blacklist/ | Auth | Отзыв refresh | AllowAny |
| POST | /api/auth/register/ | Пользователи | Регистрация читателя | AllowAny |
| GET | /api/auth/me/ | Пользователи | Текущий пользователь | IsAuthenticated |
| GET, POST | /api/books/ | Каталог | Список / создание книги | AllowAny / IsCatalogEditor |
| GET, PATCH, PUT, DELETE | /api/books/{id}/ | Каталог | Книга | AllowAny / IsCatalogEditor |
| GET, POST | /api/books/{book_id}/copies/ | Экземпляры | Список / создание | AllowAny / IsCatalogEditor |
| GET, PATCH, PUT, DELETE | /api/copies/{id}/ | Экземпляры | Экземпляр | AllowAny / IsCatalogEditor |
| GET, POST | /api/authors/ | Справочники | Авторы | AllowAny / IsCatalogEditor |
| GET, PATCH, PUT, DELETE | /api/authors/{id}/ | Справочники | Автор | AllowAny / IsCatalogEditor |
| GET, POST | /api/genres/ | Справочники | Жанры | AllowAny / IsCatalogEditor |
| GET, PATCH, PUT, DELETE | /api/genres/{id}/ | Справочники | Жанр | AllowAny / IsCatalogEditor |
| GET, POST | /api/users/ | Пользователи | Список / создание сотрудника | IsAdmin |
| GET, PATCH | /api/users/{id}/ | Пользователи | Роль и статус | IsAdmin |
| GET | /api/readers/{id}/ | Читатели | Данные читателя | IsAuthenticated |
| GET | /api/readers/{id}/issues/ | История | Выдачи читателя | IsAuthenticated |
| GET, POST | /api/issues/ | Выдача | Список / выдача | IsAuthenticated / IsLibrarianOrAdmin |
| POST | /api/issues/{id}/return/ | Возврат | Возврат книги | IsLibrarianOrAdmin |
| POST | /api/issues/{id}/mark-lost/ | Выдача | Книга утеряна | IsLibrarianOrAdmin |
| GET, POST | /api/books/{book_id}/queue/ | Очередь | Очередь на книгу | IsAuthenticated |
| GET | /api/books/{book_id}/queue/{reader_id}/position/ | Очередь | Позиция | IsAuthenticated |
| GET | /api/reservations/{id}/ | Бронирование | Состояние брони | IsAuthenticated |
| POST | /api/reservations/{id}/cancel/ | Отмена | Отмена брони | IsAuthenticated |
| GET | /api/action-log/ | Журнал | Журнал действий | IsLibrarianOrAdmin |
| GET | /api/reports/books/ | Отчёт | Отчёт по книгам | IsLibrarianOrAdmin |
| GET | /api/reports/books/export/ | Отчёт | CSV-выгрузка | IsLibrarianOrAdmin |

## 5. Замечания

- Изменения, меняющие несколько записей, выполняются в `transaction.atomic()`.
- Порядок блокировок: Book → BookCopy (по id) → Reservation (по queue_date, id)
  → Issue. Возврат книги блокирует следующую бронь до блокировки выдачи.
- Удаление книги/экземпляра защищено проверкой выдач и живых бронирований.
- Очередь ожидания реализуется через сущность `reservations`
  (см. `docs/DATABASE_DESIGN.md` и `docs/BOOK_QUEUE_DESIGN.md`).
