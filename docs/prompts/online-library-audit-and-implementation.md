# AI-Driven Development — история промптов Aider

## 2026-11-16 — Аудит и доведение онлайн-библиотеки до рабочего состояния

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

### Коммиты этапа

- `Configure Django settings for MySQL and JWT authentication`
- `Implement reader user model with roles and permissions`
- `Add JWT token endpoints and admin registration`
- `Implement library serializers for catalog, issues and reservations`
- `Implement library API views for catalog issues and queue`
- `Add backend test suite with concurrency coverage`
- `Implement action journal for library operations`
- `Add demo data loading command for library`
- `Expose user groups in reader serializer`
- `Add issue and reader list endpoints for panels`
- `Build React frontend screens for library`
