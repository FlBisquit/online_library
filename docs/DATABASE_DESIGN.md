# Проектирование базы данных — Информационная система библиотеки

## 1. Цель документа

Описать структуру базы данных информационной системы библиотеки на этапе
проектирования (без создания Django-моделей и миграций).

## 2. ER-модель (сущности и связи)

```
BOOKS ───< BOOK_COPIES
BOOKS ───< RESERVATIONS
READERS ───< ISSUES
READERS ───< RESERVATIONS
BOOK_COPIES ───< ISSUES
AUTHORS ───< BOOK_AUTHORS >── BOOKS
GENRES ───< BOOK_GENRES >── BOOKS
```

- `BOOKS` — каталог книг.
- `BOOK_COPIES` — физические экземпляры книг (одна книга = много экземпляров).
- `READERS` — читатели.
- `ISSUES` — выдачи читателей экземплярами.
- `RESERVATIONS` — бронирования книг читателями.
- `AUTHORS` / `GENRES` — справочные сущности, связанные с книгой через
  ассоциативные таблицы (M:N).

## 3. Сущности и таблицы

### 3.1. books — Книга

| Поле           | Тип          | PK / FK | Nullable | Unique | Default | Описание |
|---------------|--------------|---------|----------|--------|---------|----------|
| id            | BIGINT       | PK      | no       |        |         | идентификатор книги |
| title         | VARCHAR(500) |         | no       |        |         | название |
| description  | TEXT         |         | yes      |        |         | описание |
| isbn          | VARCHAR(20)  |         | no       | yes    |         | ISBN — уникален (защита от дублей) |
| publication_year | INTEGER  |         | yes      |        |         | год публикации |
| publisher     | VARCHAR(200) |         | yes      |        |         | издательство |

### 3.2. book_copies — Экземпляр книги

| Поле              | Тип          | PK / FK | Nullable | Unique | Default | Описание |
|------------------|--------------|---------|----------|--------|---------|----------|
| id               | BIGINT       | PK      | no       |        |         | идентификатор экземпляра |
| book_id          | BIGINT       | FK → books.id | no |    |         | связанная книга |
| inventory_number| VARCHAR(64)  |         | no       | yes    |         | уникальный инвентарный номер |
| status           | VARCHAR(20)  |         | no       |        | `AVAILABLE` | AVAILABLE / ISSUED / RESERVED / LOST / RETIRED |

**Связь «книга → экземпляры»: один ко многим (1:N).**
Одна книга каталога может иметь несколько физических экземпляров;
каждый экземпляр имеет собственный `inventory_number` и собственный
`status`, но принадлежит своей книге (`book_id`).

### 3.3. readers — Читатель

| Поле           | Тип          | PK / FK | Nullable | Unique | Default | Описание |
|---------------|--------------|---------|----------|--------|---------|----------|
| id            | BIGINT       | PK      | no       |        |         | идентификатор читателя |
| full_name     | VARCHAR(300) |         | no       |        |         | ФИО |
| email         | VARCHAR(254) |         | no       | yes    |         | контактные данные (email) |
| phone         | VARCHAR(30)  |         | yes      |        |         | телефон |
| registered_at | DATETIME    |         | no       |        | `CURRENT_TIMESTAMP` | дата регистрации |
| status        | VARCHAR(20)  |         | no       |        | `ACTIVE` | ACTIVE / BLOCKED / SUSPENDED |

### 3.4. issues — Выдача

| Поле          | Тип      | PK / FK | Nullable | Unique | Default | Описание |
|--------------|----------|---------|----------|--------|---------|----------|
| id           | BIGINT   | PK      | no       |        |         | идентификатор выдачи |
| reader_id   | BIGINT   | FK → readers.id | no |  |     | читатель |
| copy_id     | BIGINT   | FK → book_copies.id | no | |   | экземпляр |
| issued_at   | DATETIME |         | no       |        |         | дата выдачи |
| due_at      | DATETIME |         | no       |        |         | планируемая дата возврата |
| returned_at | DATETIME |         | yes      |        |         | фактическая дата возврата |
| status      | VARCHAR(20) |     | no      |        | `ISSUED` | ISSUED / RETURNED / OVERDUE / LOST |

**Ограничения целостности выдач:**
- `due_at >= issued_at`.
- `returned_at IS NULL OR returned_at >= issued_at`.
- `status = 'RETURNED'` ⇔ `returned_at IS NOT NULL`.
- `status = 'ISSUED'` ⇔ выдача активна (у экземпляра не должно быть двух
  одновременных активных выдач).

### 3.5. reservations — Бронирование

| Поле          | Тип      | PK / FK | Nullable | Unique | Default | Описание |
|--------------|----------|---------|----------|--------|---------|----------|
| id           | BIGINT   | PK      | no       |        |         | идентификатор бронирования |
| reader_id   | BIGINT   | FK → readers.id | no | |     | читатель |
| book_id     | BIGINT   | FK → books.id | no |     |     | запрошенная книга |
| status      | VARCHAR(20) |     | no      |        | `PENDING` | PENDING / ACTIVE / FULFILLED / CANCELLED |
| queue_date  | DATETIME |         | no       |        |         | дата постановки в очередь |
| expires_at  | DATETIME |         | yes      |        |         | срок действия резерва |

**Уникальность:** `UNIQUE (reader_id, book_id, status)` — защита от дублирования:
один читатель не может иметь дублирующиеся активные бронирования
на одну и ту же книгу.

### 3.6. Справочные сущности авторов и жанров (M:N)

- `authors`: id PK, full_name VARCHAR(300) NOT NULL.
- `genres`: id PK, name VARCHAR(100) NOT NULL UNIQUE.
- `book_authors`: (book_id, author_id) — составной PK, FKs → books.id, authors.id.
- `book_genres`: (book_id, genre_id) — составной PK, FKs → books.id, genres.id.

## 4. Связи между сущностями

| Связь | Тип | Описание |
|-------|-----|----------|
| books → book_copies | 1 : N | Книга имеет много экземпляров. |
| books → reservations | 1 : N | Книга может быть забронирована читателями. |
| readers → issues | 1 : N | Читатель может иметь несколько выдач. |
| readers → reservations | 1 : N | Читатель делает несколько бронирований. |
| book_copies → issues | 1 : N | Один экземпляр может выдаваться многократно (история). |
| authors → books (M:N) | M : N | Через `book_authors`. |
| genres → books (M:N) | M : N | Через `book_genres`. |

## 5. Ограничения целостности

- **Внешние ключи (FK):**
  - `book_copies.book_id → books.id` (ON DELETE CASCADE).
  - `issues.reader_id → readers.id` (ON DELETE CASCADE).
  - `issues.copy_id → book_copies.id` (ON DELETE CASCADE).
  - `reservations.reader_id → readers.id` (ON DELETE CASCADE).
  - `reservations.book_id → books.id` (ON DELETE CASCADE).
- **Проверки (CHECK):**
  - допустимые значения `status` для `book_copies`, `readers`, `issues`, `reservations`.
  - `due_at >= issued_at`.
  - `returned_at IS NULL OR returned_at >= issued_at`.

## 6. Индексы

- `books.isbn` — UNIQUE (создаётся автоматически).
- `book_copies.book_id` — индекс на FK (поиск копий книги).
- `book_copies.inventory_number` — UNIQUE (создаётся автоматически).
- `issues.reader_id` — индекс (история выдач читателя).
- `issues.copy_id` — индекс (поиск выдач экземпляра).
- `issues.status` — индекс (фильтрация активных выдач).
- `reservations.reader_id` — индекс.
- `reservations.book_id` — индекс (очереди запросов на книгу).
- `reservations (reader_id, book_id, status)` — UNIQUE + покрывающий индекс.

## 7. Защита от дублирования записей

1. **ISBN** — `UNIQUE` в таблице `books`: один ISBN = одна книга.
2. **Инвентарный номер** — `UNIQUE` в таблице `book_copies`: номер не должен
   повторяться между экземплярами.
3. **Бронирование** — `UNIQUE (reader_id, book_id, status)`: не должно быть
   двух активных бронирований одного читателя на одну книгу.
4. **Выдача** — частичный уникальный индекс
   (`UNIQUE (copy_id) WHERE status = 'ISSUED'`): экземпляр не может быть
   выдан двум читателям одновременно.

## 8. Принятые решения

- **Книга → Экземпляры: 1 : N.** Одна книга (метаданные) имеет много
  экземпляров (физические копии). Каждый экземпляр хранит свой
  инвентарный номер и свой статус (`AVAILABLE` / `ISSUED` / `RESERVED` / `LOST` / `RETIRED`).
- **Статусы** выдач и бронирований хранятся строками перечислений (enum-like)
  с CHECK-ограничениями.
- **Очередь** формируется по `queue_date` (порядок создания записи).
- **Резерв** имеет срок действия (`expires_at`); после истечения — статус
  `PENDING`/`EXPIRED`.

## 9. Что не реализовано на этом этапе

- Django-модели и миграции.
- Бизнес-логика выдачи, возврата, резервирования.
- Скрипты миграций и начальное наполнение справочников.
