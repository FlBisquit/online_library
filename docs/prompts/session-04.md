# Сессия 04 — Истечение резервов и hardening настроек

- Время: 2026-11-23 13:39–13:44 +05:00
- Текст исходного промпта в репозитории не сохранился и не восстанавливался.
  Запись составлена из фактических коммитов и предыдущих записей AI_LOG.

## Коммиты

- `0c488be Add reservation expiry management command`
- `c7e0a6a Harden Django settings, JWT lifetime and dependency requirements`

## Результат

Добавлена команда expire_reservations; BASE_DIR указывает на backend; SECRET_KEY/DATABASE_URL обязательны; DEBUG=False по умолчанию; добавлены CSRF_TRUSTED_ORIGINS; access token — 15 минут; включён throttling.

## Что пришлось исправить

Исправлены BASE_DIR (env не читался из backend/.env) и select_for_update вне transaction.atomic().
