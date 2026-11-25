# Library Management System

Web-based information system for managing a library:
book catalog, book copies, readers, issue/return of copies,
waiting queue and reservations of returned copies.

## Tech Stack

- Backend: Django + Django REST Framework
- Frontend: React (Vite)
- Database: MySQL / MariaDB
- Authentication: JWT (djangorestframework-simplejwt, refresh token blacklist)
- AI agent: Aider

## Project Structure

```
fin_proj/
├── backend/          # Django backend
│   ├── manage.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── config/       # Django project configuration
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
│   └── library/      # Django app
│       ├── admin.py
│       ├── apps.py
│       ├── models.py
│       ├── serializers.py
│       ├── services.py
│       ├── views.py
│       ├── urls.py
│       ├── permissions.py
│       ├── roles.py
│       ├── constants.py
│       ├── migrations/
│       ├── management/commands/load_demo_data.py
│       └── tests.py
├── frontend/         # React frontend
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── .env
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── styles.css
│       ├── api/
│       │   └── client.js
│       ├── auth/
│       │   └── AuthContext.jsx
│       └── pages/
│           ├── LoginPage.jsx
│           ├── CatalogPage.jsx
│           ├── MyLoansPage.jsx
│           ├── LibrarianPage.jsx
│           └── AdminPage.jsx
├── docs/
└── AI_LOG.md
```

## Run

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Linux / macOS
# venv\Scripts\activate         # Windows

pip install -r requirements.txt
cp .env.example .env             # при необходимости скорректировать DATABASE_URL / SECRET_KEY
python manage.py migrate
python manage.py load_demo_data
python manage.py runserver
```

Backend will be available at http://127.0.0.1:8000

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend will be available at http://localhost:5173

The Vite dev server proxies `/api` requests to the Django backend
(see `frontend/vite.config.js` and `frontend/.env`).

## Tests

Backend (Django REST Framework):

```bash
cd backend
python manage.py test
```

Frontend: сборка проверяется командой `npm run build`.

## Demo data

```bash
cd backend
python manage.py load_demo_data
```

Команда идемпотентна: повторный запуск обновляет существующие записи, не создавая
дубликаты. `--reset` в одной транзакции очищает данные приложения и загружает
демо-набор заново.

Демо-набор: 10 авторов, 8 жанров, 24 книги с обложками (`cover_url`), 33 экземпляра,
33 выдачи (включая `RETURNED`, `ISSUED`, `OVERDUE` и `LOST`) и 6 броней. Даты выдач
распределены по последним 60 дням. Есть книга с тремя читателями в очереди, книга
с активной бронью и экземпляром `RESERVED`, а также отменённая и истёкшая брони
за последний месяц. Один из читателей заблокирован (`reader7@library.local`).

## Test accounts

| Role               | Email                    | Password         |
|--------------------|--------------------------|------------------|
| Администратор      | admin@library.local      | AdminPass123     |
| Библиотекарь       | librarian@library.local  | LibrarianPass123 |
| Читатель           | reader0@library.local    | ReaderPass123    |
| ...                | reader1..6@library.local | ReaderPass123    |
| Читатель (BLOCKED) | reader7@library.local    | ReaderPass123    |

## Manual scenario

1. Читатель входит в очередь на книгу (`POST /api/books/<book_id>/queue/` или UI кабинета).
2. Библиотекарь принимает возврат выданной книги (`POST /api/issues/<issue_id>/return/`).
3. У читателя в кабинете появляется запись «Мои очереди и брони»: «Книга ждёт вас до дд.мм чч:мм» и позиция в очереди.
4. Библиотекарь выдаёт книгу из очереди (`POST /api/issues/`); для экземпляра со статусом `RESERVED` читатель подставляется из активной брони.
5. У читателя в разделе «Сейчас на руках» книга отображается с названием и сроком, при просрочке — красной отметкой.

Сценарий проверен на демо-книге «Анна Каренина»: очередь → возврат → активная бронь → выдача → книга «на руках».

## Environment variables (backend/.env)

```
DEBUG=True
SECRET_KEY=change-me-to-a-long-random-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1,::1
DATABASE_URL=mysql://user:password@127.0.0.1:3306/library
CORS_ALLOWED_ORIGINS=http://localhost:5173
CSRF_TRUSTED_ORIGINS=http://localhost:8000
```

Для продакшена замените значения секретов и расширьте `ALLOWED_HOSTS`.
