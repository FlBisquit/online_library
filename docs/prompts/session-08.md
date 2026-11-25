# Сессия 08 — Ленивое и cron-истечение резервов

- Время: 2026-11-23 14:47–14:53 +05:00
- Текст исходного промпта в репозитории не сохранился и не восстанавливался.
  Запись составлена из фактических коммитов и предыдущих записей AI_LOG.

## Коммиты

- `118fa13 Add regression tests for reservation expiration`
- `cbcbb1f Allow system action logs without a user`
- `8a01a91 Implement lazy and cron-driven reservation expiration with system audit logs`
- `a3ca9af Update AI log with reservation expiration fixes`

## Результат

expire_reservations() работает в одной транзакции, обрабатывает цепочку просроченных резервов, пишет системные ActionLog и вызывается лениво из пользовательских сценариев.

## Что пришлось исправить

select_for_update вне транзакции, один просроченный резерв за вызов, просроченный ACTIVE-резерв не блокировал выдачу.
