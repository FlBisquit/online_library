# Сессия 13 — Исправления по итогам аудита

- Время: 2026-11-23 16:17–16:46 +05:00
- Текст исходного промпта в репозитории не сохранился и не восстанавливался.
  Запись составлена из фактических коммитов и предыдущих записей AI_LOG.

## Коммиты

- `9d09f07 Add regression test for registration without role groups`
- `d4ac7b9 Create reader role group during registration when missing`
- `49159f3 Add regression test for manual copy status desync`
- `b88b8f9 Prevent manual copy status reset and clarify admin status options`
- `cf0e890 Add regression test for copy deletion with active reservation`
- `7ee7288 Block copy deletion while live reservations exist`
- `a01edd2 Add lock order regression test for issue return`
- `a91c3e2 Lock reservations before issues when returning books`
- `101814f Refresh API documentation for current endpoints`
- `dd4e8b5 Remove unused permission and serializer classes`
- `cf482d6 Document audit fixes and final verification`

## Результат

Регистрация создаёт группу reader на чистой БД; ручной сброс ISSUED/RESERVED запрещён; удаление с живой бронью даёт 409; порядок блокировок при возврате исправлен.

## Что пришлось исправить

Group.objects.get падал без демо-данных; статус экземпляра расходился с выдачей; удаление ломало живые брони; блокировки шли в неверном порядке.
