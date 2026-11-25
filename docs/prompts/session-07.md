# Сессия 07 — Очередь, брони и конкурентность

- Время: 2026-11-23 14:34–14:45 +05:00
- Текст исходного промпта в репозитории не сохранился и не восстанавливался.
  Запись составлена из фактических коммитов и предыдущих записей AI_LOG.

## Коммиты

- `11cca5f Add regression tests for queue and reservation bugs`
- `7e2ffdc Replace reservation status uniqueness with active slot and copy link`
- `bc6cb6a Handle database integrity errors as API conflicts`
- `0f99ea2 Serialize queue operations with consistent lock order`
- `632122b Fix queue listing privacy and join validation`
- `9d2a967 Keep BookCopy locks before Reservation locks in queue flows`
- `2b12f89 Update AI log with queue and reservation fixes`

## Результат

Уникальность активной брони переведена на active_slot, добавлен Reservation.copy, IntegrityError → 409, порядок блокировок Book → BookCopy → Reservation, читатель видит только свою позицию.

## Что пришлось исправить

TypeError из-за to_representation() у ListSerializer; unique(reader, book, status) мешал повторному join; утечка чужих позиций; 500 на несуществующую книгу.
