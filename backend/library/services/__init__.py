"""Бизнес-логика библиотеки: выдача, возврат, очередь, резервирование.

Порядок блокировок (везде одинаковый, чтобы избежать deadlock):
Book -> BookCopy (по id) -> Reservation (по queue_date, id) -> Issue.
"""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from library import constants, models
from library.transitions import ISSUE_TRANSITIONS, Conflict, change_status


def _get_reader(reader_id):
    try:
        return models.Reader.objects.get(pk=reader_id)
    except models.Reader.DoesNotExist:
        raise NotFound("Читатель не найден.")


def _log_action(user, action, details=None):
    """Запись действия пользователя в журнал (в рамках уже открытой транзакции)."""
    if user is None or not user.is_authenticated:
        return
    models.ActionLog.objects.create(user=user, action=action, details=details or {})


def _log_system_action(action, details=None):
    """Системное действие без пользователя (например, истечение резерва)."""
    models.ActionLog.objects.create(user=None, action=action, details=details or {})


def _lock_book(book_id):
    try:
        return models.Book.objects.select_for_update().get(pk=book_id)
    except models.Book.DoesNotExist:
        raise NotFound("Книга не найдена.")


def _lock_copy(copy_id):
    try:
        return models.BookCopy.objects.select_for_update().select_related("book").get(pk=copy_id)
    except models.BookCopy.DoesNotExist:
        raise NotFound("Экземпляр книги не найден.")


def _lock_reservation(reservation_id):
    try:
        return (
            models.Reservation.objects.select_for_update()
            .select_related("book", "copy")
            .get(pk=reservation_id)
        )
    except models.Reservation.DoesNotExist:
        raise NotFound("Бронирование не найдено.")


def issue_copy(reader_id, copy_id, user=None):
    """Выдача экземпляра читателю (в одной транзакции с изменением статуса)."""
    # Книгу узнаём без блокировки через экземпляр; истечение обрабатываем лениво.
    book_id = models.BookCopy.objects.filter(pk=copy_id).values_list("book_id", flat=True).first()
    if book_id is None:
        raise NotFound("Экземпляр книги не найден.")
    expired_for_reader = models.Reservation.objects.filter(
        reader_id=reader_id,
        book_id=book_id,
        status=models.Reservation.Status.ACTIVE,
        active_slot=1,
        expires_at__lt=timezone.now(),
    ).exists()
    if expired_for_reader:
        expire_reservations(book_id)
        raise Conflict("Срок действия бронирования истёк.")
    expire_reservations(book_id)

    with transaction.atomic():
        book = _lock_book(book_id)
        copy = _lock_copy(copy_id)

        reader = _get_reader(reader_id)
        if reader.status != models.Reader.Status.ACTIVE:
            raise Conflict("Читатель не может получать книги (статус BLOCKED/SUSPENDED).")

        reservation = None
        if copy.status == models.BookCopy.Status.RESERVED:
            reservation = (
                models.Reservation.objects.select_for_update()
                .filter(
                    reader=reader,
                    book=book,
                    status=models.Reservation.Status.ACTIVE,
                    active_slot=1,
                )
                .order_by("queue_date", "id")
                .first()
            )
            if reservation is None:
                raise Conflict("Экземпляр зарезервирован для другого читателя.")

        if copy.status != models.BookCopy.Status.AVAILABLE and reservation is None:
            raise Conflict("Экземпляр книги сейчас недоступен для выдачи.")

        issue = models.Issue.objects.create(
            reader=reader,
            copy=copy,
            issued_at=timezone.now(),
            due_at=timezone.now() + constants.LOAN_PERIOD,
            status=models.Issue.Status.ISSUED,
        )
        change_status(copy, models.BookCopy.Status.ISSUED, user=user)

        if reservation is not None:
            change_status(
                reservation,
                models.Reservation.Status.FULFILLED,
                user=user,
                active_slot=None,
            )

        _log_action(user, "issue.create", {"reader_id": reader.id, "copy_id": copy.id})

    return issue


def return_issue(issue_id, return_date=None, user=None):
    """Возврат экземпляра: выдача -> RETURNED, экземпляр -> AVAILABLE/RESERVED."""
    # Сначала читаем book_id/copy_id без блокировки, затем Book -> BookCopy -> Issue.
    issue_info = (
        models.Issue.objects.filter(pk=issue_id)
        .values("copy__book_id", "copy_id")
        .first()
    )
    if issue_info is None:
        raise NotFound("Выдача не найдена.")
    expire_reservations(issue_info["copy__book_id"])

    with transaction.atomic():
        book = _lock_book(issue_info["copy__book_id"])
        copy = _lock_copy(issue_info["copy_id"])
        try:
            issue = models.Issue.objects.select_for_update().select_related("reader").get(pk=issue_id)
        except models.Issue.DoesNotExist:
            raise NotFound("Выдача не найдена.")

        if models.Issue.Status.RETURNED not in ISSUE_TRANSITIONS.get(issue.status, set()):
            raise Conflict("Возврат возможен только по активной, просроченной или утерянной выдаче.")

        now = return_date or timezone.now()
        change_status(
            issue,
            models.Issue.Status.RETURNED,
            user=user,
            returned_at=now,
        )

        if copy.status != models.BookCopy.Status.AVAILABLE:
            change_status(copy, models.BookCopy.Status.AVAILABLE, user=user)

        _promote_next(book, copy, user=user)

        _log_action(user, "issue.return", {"issue_id": issue.id, "copy_id": copy.id})

        return issue


def join_queue(reader_id, book_id, user=None):
    """Добавление читателя в конец очереди ожидания (бронь PENDING)."""
    expire_reservations(book_id)
    with transaction.atomic():
        book = _lock_book(book_id)
        reader = _get_reader(reader_id)
        if reader.status != models.Reader.Status.ACTIVE:
            raise Conflict("Читатель не может встать в очередь (статус BLOCKED/SUSPENDED).")

        # Сначала BookCopy (по id), затем Reservation (по queue_date, id).
        free_copy = (
            models.BookCopy.objects.select_for_update()
            .filter(book=book, status=models.BookCopy.Status.AVAILABLE)
            .order_by("id")
            .first()
        )
        existing = (
            models.Reservation.objects.select_for_update()
            .filter(reader=reader, book=book)
            .order_by("queue_date", "id")
        )
        if any(
            row.active_slot == 1
            or row.status in (models.Reservation.Status.PENDING, models.Reservation.Status.ACTIVE)
            for row in existing
        ):
            raise Conflict("Читатель уже находится в очереди ожидания на эту книгу.")

        if free_copy is not None:
            raise Conflict("Есть свободные экземпляры книги — вставать в очередь не нужно.")

        now = timezone.now()
        reservation = models.Reservation.objects.create(
            reader=reader,
            book=book,
            copy=None,
            status=models.Reservation.Status.PENDING,
            active_slot=1,
            queue_date=now,
            expires_at=now + constants.RESERVATION_PERIOD,
        )

        _log_action(user, "queue.join", {"reader_id": reader.id, "book_id": book.id})

        return reservation


def cancel_reservation(reservation_id, user=None):
    """Отмена бронирования: освобождение её экземпляра и продвижение очереди."""
    book_id = (
        models.Reservation.objects.filter(pk=reservation_id)
        .values_list("book_id", flat=True)
        .first()
    )
    if book_id is None:
        raise NotFound("Бронирование не найдено.")
    expire_reservations(book_id)

    with transaction.atomic():
        book = _lock_book(book_id)
        # Экземпляр блокируем до бронирования (общий порядок блокировок).
        info = (
            models.Reservation.objects.filter(pk=reservation_id)
            .values("status", "copy_id")
            .first()
        )
        if info is None:
            raise NotFound("Бронирование не найдено.")
        copy = None
        if (
            info["status"] == models.Reservation.Status.ACTIVE
            and info["copy_id"]
        ):
            copy = _lock_copy(info["copy_id"])
        reservation = _lock_reservation(reservation_id)
        if reservation.status not in (
            models.Reservation.Status.PENDING,
            models.Reservation.Status.ACTIVE,
        ):
            raise Conflict("Отменить можно только активное или ожидающее бронирование.")

        if (
            reservation.status == models.Reservation.Status.ACTIVE
            and copy is not None
            and copy.status == models.BookCopy.Status.RESERVED
        ):
            change_status(copy, models.BookCopy.Status.AVAILABLE, user=user)

        change_status(
            reservation,
            models.Reservation.Status.CANCELLED,
            user=user,
            active_slot=None,
        )
        _promote_next(book, copy, user=user)

        _log_action(user, "reservation.cancel", {"reservation_id": reservation.id, "book_id": book.id})

        return reservation, copy


def _promote_next(book, available_copy, user=None):
    """Переход следующего читателя из очереди после освобождения экземпляра."""
    if available_copy is None:
        return None
    next_reservation = (
        models.Reservation.objects.select_for_update()
        .filter(book=book, status=models.Reservation.Status.PENDING, active_slot=1)
        .order_by("queue_date", "id")
        .first()
    )
    if next_reservation is None:
        return None
    change_status(
        next_reservation,
        models.Reservation.Status.ACTIVE,
        user=user,
        copy=available_copy,
        expires_at=timezone.now() + constants.RESERVATION_PERIOD,
    )
    change_status(available_copy, models.BookCopy.Status.RESERVED, user=user)
    return next_reservation


def expire_reservations(book_id=None):
    """Истечь все просроченные резервы (опционально только для одной книги).

    Работает в одной транзакции; порядок блокировок: Book -> BookCopy -> Reservation.
    После каждого истёкшего резерва освобождённый экземпляр сразу передаётся
    следующему PENDING-бронированию. Повторяем, пока просроченных нет.
    """
    with transaction.atomic():
        now = timezone.now()
        processed = []
        while True:
            expired = models.Reservation.objects.filter(
                status=models.Reservation.Status.ACTIVE,
                expires_at__lt=now,
            )
            if book_id is not None:
                expired = expired.filter(book_id=book_id)
            candidate = expired.order_by("book_id", "queue_date", "id").first()
            if candidate is None:
                break

            book = _lock_book(candidate.book_id)
            copy = None
            if candidate.copy_id:
                copy = _lock_copy(candidate.copy_id)
            reservation = _lock_reservation(candidate.pk)
            # Проверка после блокировки: состояние могло измениться.
            if (
                reservation.status != models.Reservation.Status.ACTIVE
                or reservation.expires_at is None
                or reservation.expires_at >= now
            ):
                continue

            if copy is not None and copy.status == models.BookCopy.Status.RESERVED:
                change_status(copy, models.BookCopy.Status.AVAILABLE, user=None)
            change_status(
                reservation,
                models.Reservation.Status.EXPIRED,
                user=None,
                active_slot=None,
            )

            _log_system_action(
                "reservation.expire",
                {
                    "reservation_id": reservation.id,
                    "book_id": book.id,
                    "copy_id": copy.id if copy is not None else None,
                },
            )
            _promote_next(book, copy)
            processed.append(reservation)
        return processed


def mark_overdue():
    """Перевести просроченные выдачи ISSUED в OVERDUE (UPDATE ... WHERE ...).

    Вызывается лениво при выдаче списков выдач и из management command.
    """
    with transaction.atomic():
        now = timezone.now()
        candidates = list(
            models.Issue.objects.filter(
                status=models.Issue.Status.ISSUED,
                due_at__lt=now,
            )
            .order_by("id")
            .values_list("id", "copy__book_id", "copy_id")
        )
        processed = []
        for issue_id, book_id, copy_id in candidates:
            _lock_book(book_id)
            _lock_copy(copy_id)
            try:
                issue = models.Issue.objects.select_for_update().get(pk=issue_id)
            except models.Issue.DoesNotExist:
                continue
            # Проверка после блокировки: выдача могла быть возвращена.
            if (
                issue.status != models.Issue.Status.ISSUED
                or issue.due_at >= now
            ):
                continue
            change_status(issue, models.Issue.Status.OVERDUE, user=None)
            processed.append(issue)
        return processed


def mark_issue_lost(issue_id, user=None):
    """Отметить выдачу и её экземпляр утерянными."""
    with transaction.atomic():
        info = (
            models.Issue.objects.filter(pk=issue_id)
            .values("copy__book_id", "copy_id")
            .first()
        )
        if info is None:
            raise NotFound("Выдача не найдена.")
        _lock_book(info["copy__book_id"])
        copy = _lock_copy(info["copy_id"])
        try:
            issue = models.Issue.objects.select_for_update().get(pk=issue_id)
        except models.Issue.DoesNotExist:
            raise NotFound("Выдача не найдена.")

        change_status(issue, models.Issue.Status.LOST, user=user)
        if copy.status != models.BookCopy.Status.LOST:
            change_status(copy, models.BookCopy.Status.LOST, user=user)
        _log_action(user, "issue.mark_lost", {"issue_id": issue.id, "copy_id": copy.id})
        return issue
