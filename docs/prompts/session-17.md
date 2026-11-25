# Сессия 17 — Тесты и скрипт защиты выдачи

- Время: 2026-11-26 02:06–02:15 +05:00
- Текст исходного промпта в репозитории не сохранился и не восстанавливался.
  Запись составлена из фактических коммитов и предыдущих записей AI_LOG.

## Коммиты

- `7eecf13 Use MD5 password hasher in test settings`
- `d4b54a3 Split library tests into focused modules`
- `fe4e1eb Add failing test for malformed issue ids`
- `da30d70 Validate issue ids before issuing`
- `ac53225 Persist demo login passwords`
- `ca85499 Add concurrent booking protection script`
- `7f296ba Use a fresh copy in concurrent booking check`
- `ae6e344 Document test suite and concurrency protection script`

## Результат

113 уникальных тестов в backend/library/tests/, прогон ~11 с, 10-поточные проверки, red/green для некорректных ID, скрипт scripts/concurrent_booking.py.

## Что пришлось исправить

42 заявленных теста были 24 уникальными из-за наследования; некорректные ID давали 500; демо-пароли не сохранялись; скрипту нужен был экземпляр без истории и корректный ISBN.
