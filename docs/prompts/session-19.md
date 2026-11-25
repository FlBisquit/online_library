# Сессия 19 — Приведение процессных документов и Aider-конфигурации в порядок

- Время: 2026-11-26 02:19:49–02:27:32 +05:00
- Текст исходного промпта в репозитории не сохранился и не восстанавливался:
  задача процессная, а не диалог с выдуманным текстом. Запись составлена из
  фактических коммитов. Сессия пересекалась по времени с аудитом (`session-18.md`),
  но не меняла код: аудит был только отчётом, а здесь правились документы.

## Коммиты

- `c19c816` Configure Aider with free model and history files
- `8eba60d` Add .aiderignore
- `dff6d89` Add Aider history file structure
- `7ccecf3` Add rule: lock before checks
- `2dd8176` Add rule: MySQL-only concurrency tests
- `d7ad8cf` Add rule: no manual ListSerializer representation
- `59e9f13` Add rule: one route per path
- `b233068` Add rule: assign role on user creation
- `b49dfa6` Add rule: BASE_DIR for backend env
- `133640d` Add rule: schema changes require migrations
- `eeeb4e4` Update conventions for current layout
- `7d7419a` Document honest AI session history and security audit

## Результат

`.aider.conf.yml`: бесплатная модель `gemini/gemini-2.5-flash`, `gitignore: false`,
history-файлы, `auto-commits: false`, `read: CONVENTIONS.md`. Добавлен
`.aiderignore`, history-файлы созданы как честная структура без выдуманных диалогов.
В `CONVENTIONS.md` зафиксированы семь правил по реальным ошибкам агента и правки
под актуальную структуру (`library/services/`, `library/tests/`). `AI_LOG.md`
перенесён в `docs/AI_LOG.md`, переписаны `docs/AI_REVIEW.md`, `docs/PLAN.md`,
`docs/SPEC.md`, добавлены карточки сессий.

## Что пришлось исправить

Старые документы утверждали неверное (SECRET_KEY «полностью исправлен»,
rate limiting работает, журнал действий был сначала отмечен выполненным,
SPEC написан до кода). Всё переписано по факту: открытые проблемы аудита
остались открытыми, спецификация помечена как созданная после кода.
