# Сессия 05 — Срок access token и лимит token endpoint

- Время: 2026-11-23 13:45–13:51 +05:00
- Текст исходного промпта в репозитории не сохранился и не восстанавливался.
  Запись составлена из фактических коммитов и предыдущих записей AI_LOG.

## Коммиты

- `513b785 Add scoped rate limit for token endpoint`
- `12896f7 Add access token lifetime test`
- `c2e6d74 Update AI log with access token lifetime test stage`

## Результат

Token endpoint получил отдельный лимит 10/min; тест проверяет exp - iat = 900 секунд.

## Что пришлось исправить

Позже выявлен флейк 429 в тестах, исправлен в 0adfe56.
