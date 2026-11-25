# AI_LOG — журнал задач AI-агента

Файл перенесён из корня репозитория в `docs/AI_LOG.md` (перемещение сделано
`git mv`, история файла сохранена).

## О достоверности записей

- Задачи и даты восстановлены из `git log` (время коммитов указано в `+05:00`)
  и из ранее существовавшего `AI_LOG.md`. Даты не изменялись.
- Текст исходных промптов почти не сохранялся. Он есть только для сессий 02/03
  (`docs/prompts/online-library-audit-and-implementation.md`) и 18
  (`docs/prompts/session-18.md`). Остальные файлы `docs/prompts/session-*.md`
  содержат время, коммиты, результат и исправления, но **не выдуманные диалоги**.
- Коммиты, подтверждающие каждую задачу, перечислены в соответствующем файле сессии.

## 1. 2026-11-09 — Начальная структура и проектные документы

- **Задача:** создать структуру проекта и описать предметную область.
- **Сессия:** `docs/prompts/session-01.md`, 2026-11-09 16:01–17:58 +05:00.
- **Результат:** репозиторий, документы `BUSINESS_LOGIC`, `DATABASE_DESIGN`,
  `API_DESIGN`, `BOOK_QUEUE_DESIGN`, `TEST_PLAN`, первые модели Django (`b5876b3`,
  `0401cf1`, `32a3999`, `727622e`).
- **Что пришлось исправить:** в доступных источниках не зафиксировано.

## 2. 2026-11-16 — Backend: MySQL, JWT, модели, API и тесты

- **Задача:** поднять backend библиотеки: настройки, пользователь с ролями,
  JWT, сериализаторы, views/services, тесты с конкурентной выдачей.
- **Сессия:** `docs/prompts/online-library-audit-and-implementation.md`
  (текст промпта сохранён), 2026-11-16 11:48–12:10 +05:00.
- **Результат:** коммиты `9238407`, `3bdf244`, `e41a66b`, `474b07b`, `c265dc2`,
  `c71288a`. Миграции, API каталога/выдач/очереди, `ActionLog`, 42 теста,
  `manage.py check`, `migrate`, `test` и `vite build` — зелёные.
- **Что пришлось исправить:** дублирование модели `Reader`; неверный импорт
  `Conflict` из `rest_framework.exceptions`; `get_permissions()` возвращал классы
  вместо экземпляров; таблицы `token_blacklist` ссылались на `auth_user`, потому
  что миграции применились до смены `AUTH_USER_MODEL` (пересозданы с FK на
  `library_reader`); `AllowAny`/`IsAuthenticated` вместо экземпляров прав.

## 3. 2026-11-16 — Журнал, демо-данные, фронтенд и документация

- **Задача:** довести проект от аудита до рабочего состояния: журнал действий,
  `load_demo_data`, React-экраны, проектные документы.
- **Сессия:** `docs/prompts/online-library-audit-and-implementation.md`
  (текст промпта сохранён), 2026-11-16 12:12–12:27 +05:00.
- **Результат:** `ef77a12`, `8aa18cf`, `4f27e0b`, `2faef36`, `dc58680`,
  `57405a9`, `ddfdcac`, `b8970d8`, `e661e24`. Добавлены действие выхода в
  навигации (`57405a9`) и обработка истёкших броней при продвижении очереди
  (`ddfdcac`). Созданы `docs/SPEC.md`, `docs/PLAN.md`,
  `docs/AI_REVIEW.md`, `CONVENTIONS.md`, `.aider.conf.yml`.
- **Что пришлось исправить:** расхождение с `docs/API_DESIGN.md`: публичная
  регистрация оставлена на `POST /api/readers/` как рабочая схема (позже перенесена
  на `/api/auth/register/`); выдачу экземпляра разрешено выполнять только
  библиотекарю и администратору. `docs/SPEC.md` создан **после** кода — см.
  пометку происхождения в самом файле.

## 4. 2026-11-23 — Истечение резервов и hardening настроек

- **Задача:** добавить команду истечения броней, убрать небезопасные дефолты
  настроек и задать срок access token.
- **Сессия:** `docs/prompts/session-04.md`, 2026-11-23 13:39–13:45 +05:00.
- **Результат:** `0c488be`, `5e23974`, `c7e0a6a`, `eece12e`. `BASE_DIR` указывает на `backend`,
  `SECRET_KEY` и `DATABASE_URL` обязательны, `DEBUG=False` по умолчанию,
  `CSRF_TRUSTED_ORIGINS`, access token 15 минут, DRF throttling.
- **Что пришлось исправить:** `expire_reservations()` падал с
  `TransactionManagementError: select_for_update cannot be used outside of a
  transaction` — обёрнут в `transaction.atomic()`; `BASE_DIR` сначала указывал
  на корень, поэтому `backend/.env` не читался.

## 5. 2026-11-23 — Срок access token и лимит token endpoint

- **Задача:** зафиксировать срок access token тестом и ограничить частоту
  получения токенов.
- **Сессия:** `docs/prompts/session-05.md`, 2026-11-23 13:45–13:51 +05:00.
- **Результат:** `513b785`, `12896f7`, `c2e6d74`. Scope `token`
  10/min, тест `exp - iat = 900` секунд.
- **Что пришлось исправить:** scope позже оказался не подключён из-за опечатки
  `throttling_class` (найдено аудитом 18, остаётся открытым); полный прогон
  тестов получал 429 — ослаблен в `0adfe56`.

## 6. 2026-11-23 — Регистрация, JWT-сессия и фронтенд

- **Задача:** перевести регистрацию на `/api/auth/register/`, добавить
  `/api/auth/me/`, восстановление сессии и refresh-поток на фронтенде.
- **Сессия:** `docs/prompts/session-06.md`, 2026-11-23 13:57–14:29 +05:00.
- **Результат:** `0e7c4a0`, `97629c2`, `457e164`, `e695e11`, `c0674e8`,
  `5b0ee8a`, `c277f22`, `0adfe56`, `ec3fb35`. Регистрация с валидацией пароля,
  `Reader.is_active` из статуса, logout-валидация, общий refresh-promise,
  экраны входа/регистрации.
- **Что пришлось исправить:** старый `POST /api/readers/` не назначал группу
  `reader`; полный прогон падал с 429 из-за token throttle; вечная «Загрузка...»
  из-за неинициализированного auth state.

## 7. 2026-11-23 — Очередь, бронирование и конкурентность

- **Задача:** устранить ошибки очереди, утечку чужих позиций и гонку выдачи.
- **Сессия:** `docs/prompts/session-07.md`, 2026-11-23 14:34–14:45 +05:00.
- **Результат:** `11cca5f`, `7e2ffdc`, `bc6cb6a`, `0f99ea2`, `632122b`,
  `9d2a967`, `2b12f89`. `Reservation.copy`, `active_slot`, `IntegrityError → 409`,
  порядок блокировок Book → BookCopy → Reservation → Issue, читатель видит
  только свою позицию, 10 параллельных join → 1×201 и 9×409.
- **Что пришлось исправить:** `TypeError` при ручном вызове
  `to_representation()` у `ListSerializer`; unique constraint мешал повторному
  join/cancel; утечка позиций других читателей; 500 на несуществующую книгу.

## 8. 2026-11-23 — Ленивое и cron-истечение резервов

- **Задача:** сделать истечение резервов рабочим сценарием, а не мёртвым кодом.
- **Сессия:** `docs/prompts/session-08.md`, 2026-11-23 14:47–14:53 +05:00.
- **Результат:** `118fa13`, `cbcbb1f`, `8a01a91`, `a3ca9af`. Одна транзакция,
  цепочка просроченных броней, системные `ActionLog(user=None)`, ленивый вызов
  из пользовательских сценариев и команда для cron.
- **Что пришлось исправить:** `select_for_update` вне транзакции; за один вызов
  истекал только один резерв; просроченный `ACTIVE`-резерв продолжал блокировать
  экземпляр.

## 9. 2026-11-23 — Централизованные переходы статусов

- **Задача:** заменить разбросанные проверки единой картой переходов, добавить
  OVERDUE/LOST и историю old_status/new_status.
- **Сессия:** `docs/prompts/session-09.md`, 2026-11-23 14:55–15:07 +05:00.
- **Результат:** `e4e2229`, `1bcbf28`, `a2eeb8e`, `75b324d`, `cf17f2c`,
  `1d9bf51`, `2711cd8`. `change_status()`, `mark-lost`, `mark_overdue`, возврат
  только для сотрудников.
- **Что пришлось исправить:** возврат был доступен читателю; журнал не хранил
  старый и новый статус; недопустимые переходы не блокировались.

## 10. 2026-11-23 — Журнал действий: API и экран

- **Задача:** сделать реальный `GET /api/action-log/` и экран журнала.
- **Сессия:** `docs/prompts/session-10.md`, 2026-11-23 15:10–15:26 +05:00.
- **Результат:** `7d2512f`, `d58aa31`, `521b733`, `b514647`. Пагинация, фильтры,
  `assertNumQueries(3)`, вкладка «Журнал» в админке и панели библиотекаря.
- **Что пришлось исправить:** `docs/PLAN.md` ошибочно отмечал пункт выполненным,
  хотя эндпоинта и экрана не было; исправление зафиксировано в `521b733`.

## 11. 2026-11-23 — Отчёт по книгам и CSV

- **Задача:** заменить старые отчёты агрегированным отчётом за период с CSV.
- **Сессия:** `docs/prompts/session-11.md`, 2026-11-23 15:29–15:47 +05:00.
- **Результат:** `cb2a568`, `a7d2a29`, `09db97b`, `19bee6c`, `102a401`,
  `0213e9f`, `0080cb2`, `62fe1eb`. Один SQL-запрос, BOM `utf-8-sig`,
  экранирование `= + - @`, вкладка «Отчёт» в UI.
- **Что пришлось исправить:** у старых отчётов не было периода, они ломали даты
  (500), теряли книги без выдач и не экранировали формулы CSV.

## 12. 2026-11-23 — Каталог и управление пользователями

- **Задача:** CRUD каталога, админские экраны, управление ролями и статусами.
- **Сессия:** `docs/prompts/session-12.md`, 2026-11-23 15:51–16:12 +05:00.
- **Результат:** `5e2712b`, `b0b4b10`, `0973b5a`, `e1b3705`, `62b5ed5`,
  `d2c44b0`. `IsCatalogEditor`, `/api/users/` только для администратора,
  AdminPage с вкладками.
- **Что пришлось исправить:** дублирующий/перекрытый маршрут `/api/readers/`
  удалён — список пользователей живёт на `/api/users/`; добавлена защита себя
  и последнего администратора.

## 13. 2026-11-23 — Исправления по итогам аудита

- **Задача:** проверить уже сданный функционал на чистой БД и устранить найденные
  ошибки.
- **Сессия:** `docs/prompts/session-13.md`, 2026-11-23 16:17–16:46 +05:00.
- **Результат:** `9d09f07`, `d4ac7b9`, `49159f3`, `b88b8f9`, `cf0e890`,
  `7ee7288`, `a01edd2`, `a91c3e2`, `101814f`, `dd4e8b5`, `cf482d6`.
  Регистрация создаёт группу `reader` на чистой БД; ручной сброс
  `ISSUED`/`RESERVED` запрещён; удаление с живой бронью → 409.
- **Что пришлось исправить:** `Group.objects.get` падал без демо-данных; статус
  экземпляра расходился с выдачей; удаление ломало живые брони; при возврате
  блокировки шли в неверном порядке.

## 14. 2026-11-23 / 2026-11-25 — Кабинет читателя и панель библиотекаря

- **Задача:** перевести экраны с id-only данных на человекочитаемые и добавить
  фильтры/действия.
- **Сессия:** `docs/prompts/session-14.md`, 2026-11-23 16:53;
  2026-11-25 10:46–10:56 +05:00.
- **Результат:** `1acff99`, `2ce8d92`, `e948f8c`, `599b1d3`, `5390617`,
  `f876454`. Вложенные `book`/`reader`/`copy`, `GET /api/auth/me/reservations/`,
  фильтры `due`/`search`, «Сейчас на руках», ручной сценарий в README.
- **Что пришлось исправить:** списки были id-only; в бронях не было имени
  читателя (`e948f8c`).

## 15. 2026-11-26 — Идемпотентная загрузка демо-данных

- **Задача:** устранить `IntegrityError` при повторном запуске и сделать набор
  реалистичным.
- **Сессия:** `docs/prompts/session-15.md`, 2026-11-26 01:42 +05:00.
- **Результат:** `ca8a1bb`, `f989715`, `ffa7381`, `870705f`. `Book.cover_url`,
  24 книги, 33 экземпляра, 33 выдачи, 6 броней, `--reset` в одной транзакции,
  10 тестов на инварианты.
- **Что пришлось исправить:** повторный запуск создавал дубли авторов/жанров и
  падал; статусы и даты были непоследовательны; демо-пароли не сохранялись.

## 16. 2026-11-26 — Поиск читателя для библиотекаря

- **Задача:** добавить поиск читателя по email/ФИО для формы выдачи.
- **Сессия:** `docs/prompts/session-16.md`, 2026-11-26 01:54–01:55 +05:00.
- **Результат:** `8a69008`, `4e03029`, `93cfb90`, `fefee9a`.
  `GET /api/readers/search/` для сотрудников, подсветка просрочек и сроков
  броней, red/green-тесты доступа.
- **Что пришлось исправить:** форма искала читателя через неподходящий
  эндпоинт и получала 404.

## 17. 2026-11-26 — Тесты и скрипт защиты от гонки выдачи

- **Задача:** сделать тесты уникальными и быстрыми, проверить защиту от двойной
  выдачи через реальный HTTP API.
- **Сессия:** `docs/prompts/session-17.md`, 2026-11-26 02:06–02:15 +05:00.
- **Результат:** `7eecf13`, `d4b54a3`, `fe4e1eb`, `da30d70`, `ac53225`,
  `ca85499`, `7f296ba`, `ae6e344`. Пакет `backend/library/tests/`, 113
  уникальных тестов за ~10,9 с, `scripts/concurrent_booking.py`; два прогона
  на MySQL: `201: 1, 409: 9`, `Issue rows for this copy: 1`.
- **Что пришлось исправить:** 42 «теста» были 24 уникальными из-за наследования
  фикстур; некорректные ID давали 500; демо-пароли не сохранялись; скрипту нужен
  был экземпляр без истории выдач и существующий ISBN.

## 18. 2026-11-26 — Аудит безопасности (только отчёт)

- **Задача:** проверить IDOR по каждому эндпоинту, JWT, SQL-инъекции, валидацию,
  CSV-инъекции, утечки в сериализаторах, DEBUG, ALLOWED_HOSTS, CORS, rate limiting.
- **Сессия:** `docs/prompts/session-18.md`, 2026-11-26T02:22:23+05:00.
- **Результат:** отчёт в `docs/AI_REVIEW.md`. Код в этой сессии не менялся;
  реальный IDOR, SQL-инъекции и утечки паролей не найдены; открыты слабый
  `SECRET_KEY` в `.env.example`, `DEBUG=True` в локальном `.env`, неработающий
  scope `token`, 500 на невалидных параметрах и неполное экранирование CSV.
- **Что пришлось исправить:** не применялось — сессия была аудиторской; часть
  найденного закрыта более ранними коммитами, остальное зафиксировано как открытое.

## 19. 2026-11-26 — Приведение процессных документов и Aider-конфигурации

- **Задача:** убрать расхождения в `CONVENTIONS.md`, `.aider.conf.yml`,
  `.aiderignore`, `docs/`; перенести AI-журнал в `docs/` и не выдумывать историю
  промптов.
- **Сессия:** `docs/prompts/session-19.md`, 2026-11-26 02:19:49–02:27:32 +05:00.
- **Результат:** `c19c816`, `8eba60d`, `dff6d89`, `7ccecf3`, `2dd8176`,
  `d7ad8cf`, `59e9f13`, `b233068`, `b49dfa6`, `133640d`, `eeeb4e4`, `7d7419a`.
  Бесплатная модель в Aider, history-файлы и `.aiderignore`, семь правил агента,
  честные `docs/AI_LOG.md`, `docs/AI_REVIEW.md`, `docs/PLAN.md`, `docs/SPEC.md`.
- **Что пришлось исправить:** ложные утверждения старых документов (SECRET_KEY,
  rate limiting, журнал действий, «SPEC до кода»); пропущенные коммиты в журнале
  (`57405a9`, `5e23974`, `eece12e`, конфигурационные коммиты) добавлены при
  повторной сверке с `git log`.

## 20. 2026-11-26 — Проверка рутов, логики, тестов и покрытия логами

- **Задача:** проверить, всё ли работает; перепроверить все руты и код на
  логические ошибки; прогнать все тесты заново; обеспечить покрытие всего
  проекта логами. Выбран вариант «починить всё с тестами».
- **Сессия:** `docs/prompts/session-20.md`. Текст исходного промпта дословно
  не сохранился; карточка составлена из фактических коммитов и результатов.
- **Результат:** `c4c365e` (14 пропущенных хешей добавлены в лог и карточки
  сессий), `cfca710` (21 новый регрессионный тест), `2dfb338` (ещё 3 теста;
  владение бронью, списание, продвижение очереди), `09f0b18` (валидация,
  throttle scope, CSV, отчёты, демо-данные), `8610ca6` (фронтенд).
  Итог: 136 тестов — `OK`,
  `manage.py check` — без ошибок, `makemigrations --check --dry-run` — изменений
  нет, `npm run build` — успешно. Текущая версия документации фиксируется
  коммитом `0dabbfd`; настоящая сверка логов сделана следующим коммитом
  (он не может сослаться на собственный хеш).
- **Что пришлось исправить:** бронь можно было выдать другому экземпляру/читателю;
  списание экземпляра не блокировалось открытой выдачей; унаследованные
  `RETIRED`-состояния ломали возврат и истечение; повторный демо-запуск
  сбрасывал статусы; 500 на невалидных query/body ID; мёртвый throttle scope
  логина; неполное экранирование CSV; неверные действия в UI. Подробности —
  раздел 8 `docs/AI_REVIEW.md`.

## Ошибки агента

### 1. `BASE_DIR` указывал на корень репозитория

- **Что сделал неверно:** в `backend/config/settings.py` путь был
  `Path(__file__).resolve().parent.parent.parent`, поэтому `env.read_env()`
  искал `.env` не в `backend/`.
- **Как обнаружено:** `backend/.env` не влиял на запуск; неверный `DATABASE_URL`
  приводил к падению `migrate`, а после удаления `SECRET_KEY` из `.env` —
  `ImproperlyConfigured: Set the SECRET_KEY environment variable`.
- **Как исправлено:** `BASE_DIR = Path(__file__).resolve().parent.parent`;
  правило зафиксировано в `CONVENTIONS.md` (`b49dfa6`).
- **Коммит:** `c7e0a6a`.

### 2. `TypeError` при выводе очереди

- **Что сделал неверно:** view очереди вызывал
  `serializer.to_representation(reservation)` вручную у `ListSerializer` (`many=True`),
  который ожидает список, а не один объект. `GET /api/books/<id>/queue/` давал 500.
- **Как обнаружено:** регрессионный тест
  `test_queue_list_reader_sees_only_own_position_and_total` (`11cca5f`) и ручной
  запрос к эндпоинту.
- **Как исправлено:** сериализация каждого объекта через обычный сериализатор;
  читателю отдаются только его позиция и `total`. Правило добавлено в
  `CONVENTIONS.md` (`d7ad8cf`).
- **Коммит:** `632122b`.

### 3. Unique constraint блокировал повторный вход в очередь

- **Что сделал неверно:** ограничение `unique(reader, book, status)` запрещало
  второй `PENDING` после цикла join → cancel → join.
- **Как обнаружено:** тест `test_join_cancel_cycle_can_repeat_five_times` (`11cca5f`)
  и 500/409 на повторном вступлении.
- **Как исправлено:** уникальность перенесена на `active_slot` (1 для
  `PENDING`/`ACTIVE`, NULL иначе), добавлен `Reservation.copy` и data migration
  `0005_reservation_active_slot_and_copy`; правило о миграциях — `133640d`.
- **Коммит:** `7e2ffdc`.

### 4. Перекрытый маршрут `readers/`

- **Что сделал неверно:** вместе с новым админским списком пользователей
  сохранялся старый `path("readers/", ReaderListView)`, из-за чего маршруты
  `/api/readers/`, `/api/readers/search/` и `/api/users/` конфликтовали.
- **Как обнаружено:** тест `test_duplicate_readers_route_is_removed` (`0973b5a`):
  `GET /api/readers/` должен был дать 404, но возвращал список; также 405 на
  старом эндпоинте.
- **Как исправлено:** дубль удалён, список пользователей оставлен только на
  `/api/users/`, поиск — на `/api/readers/search/`; правило «один маршрут на
  путь» — `59e9f13`.
- **Коммит:** `e1b3705`.

### 5. Пользователь без роли

- **Что сделал неверно:** при регистрации вызывался
  `Group.objects.get(name="reader")`. На чистой БД без демо-данных группы не
  существовала, регистрация падала.
- **Как обнаружено:** регрессионный тест на регистрацию без групп `9d09f07`
  (`DoesNotExist` → 500).
- **Как исправлено:** `Group.objects.get_or_create(name=roles.READER_ROLE)` в
  `RegisterView.perform_create`; правило зафиксировано в `b233068`.
- **Коммит:** `d4ac7b9`.

### 6. `select_for_update` вне транзакции

- **Что сделал неверно:** `expire_reservations()` вызывал `select_for_update()`
  без `transaction.atomic()`.
- **Как обнаружено:** `TransactionManagementError: select_for_update cannot be
  used outside of a transaction` при запуске команды истечения броней.
- **Как исправлено:** функция обёрнута в `transaction.atomic()`, блокировки
  идут до проверок в порядке Book → BookCopy → Reservation; правило — `7ccecf3`.
- **Коммит:** `0c488be`.

### 7. Некорректные ID при выдаче

- **Что сделал неверно:** `reader_id`/`copy_id` из тела запроса попадали в ORM
  без проверки типа; строка `abc` вызывала `ValueError` → 500.
- **Как обнаружено:** red-тест `fe4e1eb Add failing test for malformed issue ids`.
- **Как исправлено:** явная проверка целочисленности, некорректные значения
  дают 400.
- **Коммит:** `da30d70`.

### 8. Демо-пароли не сохранялись

- **Что сделал неверно:** `load_demo_data` вызывал `set_password()`, но не
  сохранял пользователей, поэтому логины из README не работали.
- **Как обнаружено:** тест `test_demo_users_have_readme_passwords`, добавленный
  вместе с исправлением.
- **Как исправлено:** `_ensure_password()` сохраняет пользователя после смены
  пароля.
- **Коммит:** `ac53225`.

### 9. Опечатка `throttling_class` отключала лимит логина

- **Что сделал неверно:** в `backend/library/urls.py` было написано
  `TokenObtainPairView.throttling_class = ScopedRateThrottle`; в DRF атрибут
  называется `throttle_classes`, поэтому scope `token` 10/min не применялся.
- **Как обнаружено:** аудит 18 проверил список throttle-классов через Django
  shell; повторная проверка зафиксировала регрессионным тестом (`cfca710`).
- **Как исправлено:** выделен `ScopedTokenObtainPairView` с
  `throttle_classes = [ScopedRateThrottle]` и `throttle_scope = "token"`.
- **Коммит:** `09f0b18`.

### 10. Активная бронь не привязывалась к экземпляру при выдаче

- **Что сделал неверно:** `issue_copy()` искал бронь читателя без фильтра
  `copy_id`; зарезервированный экземпляр могли выдать другому читателю, а
  читатель с активной бронью — взять любой свободный экземпляр.
- **Как обнаружено:** регрессионные тесты `cfca710` показали, что конфликт не
  возникает там, где должен.
- **Как исправлено:** бронь проверяется по `copy_id`, активная бронь блокирует
  выдачу другого экземпляра; добавлены проверки `copy_id` после блокировки.
- **Коммит:** `2dfb338`.

### 11. Повторный `load_demo_data` перезаписывал статусы экземпляров

- **Что сделал неверно:** `update_or_create(..., defaults={"status": "AVAILABLE"})`
  сбрасывал `ISSUED`/`RESERVED`/`LOST` при повторной загрузке демо-данных.
- **Как обнаружено:** тест `test_rerun_preserves_copy_statuses` (`cfca710`).
- **Как исправлено:** `get_or_create` и финальная сверка статусов из Issues
  и Reservations; повторный вызов теперь идемпотентен по статусам.
- **Коммит:** `09f0b18`.

## Приложение A — полный индекс коммитов

Сверка с `git log` после правки документации: 123 коммита, от `b5876b3` до
`0dabbfd`. Каждый хеш встречается либо в записи `docs/AI_LOG.md`, либо в
карточке сессии в `docs/prompts/`, либо в этом индексе. Коммит с текущей
правкой лога не может сослаться на собственный хеш; он будет покрыт при
следующей сверке.

- `0dabbfd` 2026-11-26T03:00:11+05:00 — Reconcile process docs with audit fixes and final verification
- `8610ca6` 2026-11-26T02:51:22+05:00 — Fix reader return button and download token refresh
- `09f0b18` 2026-11-26T02:51:22+05:00 — Fix validation, throttle, reports and demo data bugs
- `2dfb338` 2026-11-26T02:46:36+05:00 — Fix reservation ownership and retired copy state bugs
- `cfca710` 2026-11-26T02:43:43+05:00 — Add regression tests for audit findings
- `c4c365e` 2026-11-26T02:37:27+05:00 — Complete AI log coverage for all commits
- `7d7419a` 2026-11-26T02:27:32+05:00 — Document honest AI session history and security audit
- `eeeb4e4` 2026-11-26T02:22:13+05:00 — Update conventions for current layout
- `133640d` 2026-11-26T02:21:57+05:00 — Add rule: schema changes require migrations
- `b49dfa6` 2026-11-26T02:21:04+05:00 — Add rule: BASE_DIR for backend env
- `b233068` 2026-11-26T02:20:54+05:00 — Add rule: assign role on user creation
- `59e9f13` 2026-11-26T02:20:42+05:00 — Add rule: one route per path
- `d7ad8cf` 2026-11-26T02:20:30+05:00 — Add rule: no manual ListSerializer representation
- `2dd8176` 2026-11-26T02:20:20+05:00 — Add rule: MySQL-only concurrency tests
- `7ccecf3` 2026-11-26T02:20:11+05:00 — Add rule: lock before checks
- `dff6d89` 2026-11-26T02:20:01+05:00 — Add Aider history file structure
- `8eba60d` 2026-11-26T02:19:54+05:00 — Add .aiderignore
- `c19c816` 2026-11-26T02:19:49+05:00 — Configure Aider with free model and history files
- `ae6e344` 2026-11-26T02:15:23+05:00 — Document test suite and concurrency protection script
- `7f296ba` 2026-11-26T02:13:30+05:00 — Use a fresh copy in concurrent booking check
- `ca85499` 2026-11-26T02:10:24+05:00 — Add concurrent booking protection script
- `ac53225` 2026-11-26T02:09:48+05:00 — Persist demo login passwords
- `da30d70` 2026-11-26T02:07:32+05:00 — Validate issue ids before issuing
- `fe4e1eb` 2026-11-26T02:07:10+05:00 — Add failing test for malformed issue ids
- `d4b54a3` 2026-11-26T02:06:45+05:00 — Split library tests into focused modules
- `7eecf13` 2026-11-26T02:06:28+05:00 — Use MD5 password hasher in test settings
- `fefee9a` 2026-11-26T01:55:14+05:00 — Document librarian reader search and manual scenario
- `93cfb90` 2026-11-26T01:55:08+05:00 — Highlight overdue loans and active reservation deadlines
- `4e03029` 2026-11-26T01:55:03+05:00 — Use reader search endpoint in librarian panel
- `8a69008` 2026-11-26T01:54:58+05:00 — Allow librarians to search readers by email or name
- `870705f` 2026-11-26T01:42:45+05:00 — Document demo data loader behavior and checks
- `ffa7381` 2026-11-26T01:42:41+05:00 — Cover demo loader idempotency and state invariants
- `f989715` 2026-11-26T01:42:37+05:00 — Make demo data loader idempotent and realistic
- `ca8a1bb` 2026-11-26T01:42:34+05:00 — Add book cover URL to model and serializer
- `f876454` 2026-11-25T10:56:22+05:00 — Document reader and librarian completion
- `5390617` 2026-11-25T10:52:26+05:00 — Document reader and librarian manual scenario
- `599b1d3` 2026-11-25T10:52:05+05:00 — Implement reader loans and librarian panel UI
- `e948f8c` 2026-11-25T10:50:13+05:00 — Add reader names to reservation serializer
- `2ce8d92` 2026-11-25T10:46:47+05:00 — Add reader loans and librarian panel APIs
- `1acff99` 2026-11-23T16:53:46+05:00 — Add backend tests for reader loans and librarian panel
- `cf482d6` 2026-11-23T16:46:39+05:00 — Document audit fixes and final verification
- `dd4e8b5` 2026-11-23T16:42:41+05:00 — Remove unused permission and serializer classes
- `101814f` 2026-11-23T16:38:56+05:00 — Refresh API documentation for current endpoints
- `a91c3e2` 2026-11-23T16:34:16+05:00 — Lock reservations before issues when returning books
- `a01edd2` 2026-11-23T16:30:22+05:00 — Add lock order regression test for issue return
- `7ee7288` 2026-11-23T16:29:07+05:00 — Block copy deletion while live reservations exist
- `cf0e890` 2026-11-23T16:25:32+05:00 — Add regression test for copy deletion with active reservation
- `b88b8f9` 2026-11-23T16:25:04+05:00 — Prevent manual copy status reset and clarify admin status options
- `49159f3` 2026-11-23T16:21:11+05:00 — Add regression test for manual copy status desync
- `d4ac7b9` 2026-11-23T16:20:50+05:00 — Create reader role group during registration when missing
- `9d09f07` 2026-11-23T16:17:24+05:00 — Add regression test for registration without role groups
- `d2c44b0` 2026-11-23T16:12:23+05:00 — Document catalog and user management features
- `62b5ed5` 2026-11-23T16:10:43+05:00 — Rebuild admin UI for catalog and user management
- `e1b3705` 2026-11-23T16:01:41+05:00 — Implement admin-only user management API
- `0973b5a` 2026-11-23T15:56:49+05:00 — Add user management regression tests
- `b0b4b10` 2026-11-23T15:55:50+05:00 — Implement catalog CRUD and editor permissions
- `5e2712b` 2026-11-23T15:51:03+05:00 — Add catalog management regression tests
- `62fe1eb` 2026-11-23T15:47:46+05:00 — Document rewritten book report
- `0080cb2` 2026-11-23T15:47:10+05:00 — Add book report UI with CSV download
- `0213e9f` 2026-11-23T15:43:18+05:00 — Add UTF-8 BOM CSV export for book report
- `102a401` 2026-11-23T15:39:51+05:00 — Add book report CSV regression tests
- `19bee6c` 2026-11-23T15:39:04+05:00 — Replace issue reports with aggregated book report API
- `09db97b` 2026-11-23T15:34:48+05:00 — Add book report API regression tests
- `a7d2a29` 2026-11-23T15:33:52+05:00 — Track reservation cancellation time and report indexes
- `cb2a568` 2026-11-23T15:29:59+05:00 — Add cancellation timestamp regression tests
- `b514647` 2026-11-23T15:26:10+05:00 — Document action log API and UI work
- `521b733` 2026-11-23T15:23:02+05:00 — Add action log screen to admin and librarian panels, correct plan
- `d58aa31` 2026-11-23T15:11:48+05:00 — Add paginated filtered action log API for staff
- `7d2512f` 2026-11-23T15:10:01+05:00 — Add action log API regression tests
- `2711cd8` 2026-11-23T15:07:09+05:00 — Update AI log with status transition and audit changes
- `1d9bf51` 2026-11-23T15:04:32+05:00 — Add mark_overdue management command for cron
- `cf17f2c` 2026-11-23T15:04:21+05:00 — Restrict returns to staff, add mark-lost endpoint and lazy overdue marking
- `75b324d` 2026-11-23T15:01:09+05:00 — Route all service status changes through centralized transition helper
- `a2eeb8e` 2026-11-23T14:56:33+05:00 — Add centralized status transition map and transactional change_status
- `1bcbf28` 2026-11-23T14:56:13+05:00 — Add status transition fields and indexes to action log
- `e4e2229` 2026-11-23T14:55:51+05:00 — Add regression tests for status transitions, overdue and lost issues
- `a3ca9af` 2026-11-23T14:53:19+05:00 — Update AI log with reservation expiration fixes
- `8a01a91` 2026-11-23T14:52:51+05:00 — Implement lazy and cron-driven reservation expiration with system audit logs
- `cbcbb1f` 2026-11-23T14:48:09+05:00 — Allow system action logs without a user
- `118fa13` 2026-11-23T14:47:44+05:00 — Add regression tests for reservation expiration
- `2b12f89` 2026-11-23T14:45:25+05:00 — Update AI log with queue and reservation fixes
- `9d2a967` 2026-11-23T14:45:03+05:00 — Keep BookCopy locks before Reservation locks in queue flows
- `632122b` 2026-11-23T14:42:52+05:00 — Fix queue listing privacy and join validation
- `0f99ea2` 2026-11-23T14:36:52+05:00 — Serialize queue operations with consistent lock order
- `bc6cb6a` 2026-11-23T14:35:39+05:00 — Handle database integrity errors as API conflicts
- `7e2ffdc` 2026-11-23T14:35:10+05:00 — Replace reservation status uniqueness with active slot and copy link
- `11cca5f` 2026-11-23T14:34:15+05:00 — Add regression tests for queue and reservation bugs
- `ec3fb35` 2026-11-23T14:29:05+05:00 — Update AI log with frontend auth task completion
- `0adfe56` 2026-11-23T14:28:49+05:00 — Relax token rate limit during library test runs
- `c277f22` 2026-11-23T14:16:39+05:00 — Use shared loading empty and error components in screens
- `5b0ee8a` 2026-11-23T14:16:39+05:00 — Clear session and handle token refresh failure
- `c0674e8` 2026-11-23T14:07:35+05:00 — Improve API client refresh flow and fix auth session handling
- `19eb8d8` 2026-11-23T14:03:31+05:00 — Update AI log with registration and auth task completion
- `e695e11` 2026-11-23T14:03:04+05:00 — Use current user endpoint in frontend auth flow
- `457e164` 2026-11-23T14:01:52+05:00 — Add current user endpoint and logout validation tests
- `97629c2` 2026-11-23T13:59:43+05:00 — Use reader status as user active flag
- `0e7c4a0` 2026-11-23T13:57:21+05:00 — Implement public reader registration endpoint with password validation
- `c2e6d74` 2026-11-23T13:51:10+05:00 — Update AI log with access token lifetime test stage
- `12896f7` 2026-11-23T13:50:51+05:00 — Add access token lifetime test
- `513b785` 2026-11-23T13:45:34+05:00 — Add scoped rate limit for token endpoint
- `eece12e` 2026-11-23T13:44:48+05:00 — Update AI log with settings hardening stage
- `c7e0a6a` 2026-11-23T13:44:23+05:00 — Harden Django settings, JWT lifetime and dependency requirements
- `5e23974` 2026-11-23T13:39:55+05:00 — Update AI log with reservation expiry stage
- `0c488be` 2026-11-23T13:39:27+05:00 — Add reservation expiry management command
- `e661e24` 2026-11-16T12:27:24+05:00 — Update AI log and project plan with final state
- `57405a9` 2026-11-16T12:26:20+05:00 — Add logout action to frontend navigation
- `ddfdcac` 2026-11-16T12:26:20+05:00 — Handle expired reservations during queue promotion
- `b8970d8` 2026-11-16T12:24:26+05:00 — Update project documentation and AI assistant files
- `dc58680` 2026-11-16T12:21:22+05:00 — Build React frontend screens for library
- `2faef36` 2026-11-16T12:17:57+05:00 — Expose user groups in reader serializer
- `4f27e0b` 2026-11-16T12:16:08+05:00 — Add issue and reader list endpoints for panels
- `8aa18cf` 2026-11-16T12:14:18+05:00 — Add demo data loading command for library
- `ef77a12` 2026-11-16T12:12:52+05:00 — Implement action journal for library operations
- `c71288a` 2026-11-16T12:10:45+05:00 — Add backend test suite with concurrency coverage
- `c265dc2` 2026-11-16T12:00:25+05:00 — Implement library API views for catalog issues and queue
- `474b07b` 2026-11-16T11:52:23+05:00 — Implement library serializers for catalog, issues and reservations
- `e41a66b` 2026-11-16T11:51:08+05:00 — Add JWT token endpoints and admin registration
- `3bdf244` 2026-11-16T11:50:21+05:00 — Implement reader user model with roles and permissions
- `9238407` 2026-11-16T11:48:15+05:00 — Configure Django settings for MySQL and JWT authentication
- `727622e` 2026-11-09T17:58:31+05:00 — Implement Django models and add remaining design docs
- `32a3999` 2026-11-09T16:08:18+05:00 — Add database design documentation for library system
- `0401cf1` 2026-11-09T16:08:11+05:00 — Add business logic documentation for library system
- `b5876b3` 2026-11-09T16:01:40+05:00 — Initial project structure for library management system
