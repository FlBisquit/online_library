# AI-Driven Development — история промптов Aider

## 2026-11-16 — Аудит и доведение онлайн-библиотеки до рабочего состояния

Время сессий (из фактических времени коммитов):
- Сессия 02 — 2026-11-16 11:48–12:10 +05:00.
- Сессия 03 — 2026-11-16 12:12–12:27 +05:00.

Один сохранённый промпт относился к обеим сессиям; он приведён ниже без изменений.

### Промпт (prompt)

```
Задача: аудит проекта и план полного завершения онлайн-библиотеки.

Необходимо довести текущий проект онлайн-библиотеки до полностью рабочего состояния в соответствии
с требованиями учебного задания AI Driven Development.

Работай непосредственно с существующим репозиторием. Не создавай новый проект и не переписывай готовые
части без необходимости.

1. Сначала проведи аудит и составь список уже реализованных и недостающих функций.
2. Не останавливайсь после составления плана: после аудита приступай к первой незавершённой задаче
   и выполняй работу по правилам выше.

Главная цель — полностью готовая онлайн-библиотека, которую можно запустить с чистой базой данных,
протестировать и защитить преподавателю.
```

### События сессии

- Проведён аудит репозитория (README, docs, backend, frontend, git-история).
- Зафиксированы отсутствующие документы: `docs/SPEC.md`, `docs/PLAN.md`, `docs/AI_REVIEW.md`,
  `docs/prompts/`, `CONVENTIONS.md`, `.aider.conf.yml`.
- Начато выполнение этапов: настройка Django (MySQL, JWT, env), модель Reader с ролями,
  миграции, сериализаторы, API views/services, тесты, журнал действий, demo data, фронтенд.
- Все этапы сопровождались проверками (`manage.py check`, `manage.py test`, `vite build`) и Git-коммитами.

### Коммиты сессии 02 (backend)

- `9238407` Configure Django settings for MySQL and JWT authentication
- `3bdf244` Implement reader user model with roles and permissions
- `e41a66b` Add JWT token endpoints and admin registration
- `474b07b` Implement library serializers for catalog, issues and reservations
- `c265dc2` Implement library API views for catalog issues and queue
- `c71288a` Add backend test suite with concurrency coverage

### Коммиты сессии 03 (журнал, демо-данные, фронтенд, документы)

- `ef77a12` Implement action journal for library operations
- `8aa18cf` Add demo data loading command for library
- `4f27e0b` Add issue and reader list endpoints for panels
- `2faef36` Expose user groups in reader serializer
- `dc58680` Build React frontend screens for library
- `57405a9` Add logout action to frontend navigation
- `ddfdcac` Handle expired reservations during queue promotion
- `b8970d8` Update project documentation and AI assistant files
- `e661e24` Update AI log and project plan with final state
