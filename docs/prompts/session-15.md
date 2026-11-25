# Сессия 15 — Идемпотентная загрузка демо-данных

- Время: 2026-11-26 01:42 +05:00
- Текст исходного промпта в репозитории не сохранился и не восстанавливался.
  Запись составлена из фактических коммитов и предыдущих записей AI_LOG.

## Коммиты

- `ca8a1bb Add book cover URL to model and serializer`
- `f989715 Make demo data loader idempotent and realistic`
- `ffa7381 Cover demo loader idempotency and state invariants`
- `870705f Document demo data loader behavior and checks`

## Результат

cover_url, 24 книги, 33 экземпляра, 33 выдачи, 6 броней; --reset в одной транзакции; инварианты статусов и дат.

## Что пришлось исправить

Повторный запуск давал IntegrityError и дубли жанров/авторов; статусы и даты были непоследовательны.
