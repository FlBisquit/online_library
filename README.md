# Library Management System

Web-based information system for managing a library:
book catalog, book copies, readers, issue/return of copies,
waiting queue and reservations of returned copies.

## Tech Stack

- Backend: Django + Django REST Framework
- Frontend: React
- Database: SQLite (for initial development)

## Project Structure

```
fin_proj/
├── backend/          # Django backend
│   ├── manage.py
│   ├── requirements.txt
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
│       ├── views.py
│       ├── urls.py
│       └── tests.py
├── frontend/         # React frontend
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── .env
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       └── api/
│           └── client.js
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
