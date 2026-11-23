"""Бизнес-логика библиотеки: выдача, возврат, очередь, резервирование.

Порядок блокировок (везде одинаковый, чтобы избежать deadlock):
Book -> BookCopy (по id) -> Reservation (по queue_date, id) -> Issue.
"""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, NotFound

from library import constants, models


class Conflict(APIException):
    """Конфликт — операция не может быть выполнена (например, недоступный экземпляр)."""

    status_code = 409
    default_detail = "Запрос конфликтует с текущим состоянием ресурса."


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


def _clear_reservation_slot(reservation):
    reservation.status = models.Reservation.Status.CANCELLED
    reservation.active_slot = None
    reservation.save(update_fields=["status", "active_slot"])


def issue_copy(reader_id, copy_id, user=None):
    """Выдача экземпляра читателю (в одной транзакции с изменением статуса)."""
    with transaction.atomic():
        # Book блокируется первым: книгу узнаём без блокировки через экземпляр.
        book_id = models.BookCopy.objects.filter(pk=copy_id).values_list("book_id", flat=True).first()
        if book_id is None:
            raise NotFound("Экземпляр книги не найден.")
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
        copy.status = models.BookCopy.Status.ISSUED
        copy.save(update_fields=["status"])

        if reservation is not None:
            reservation.status = models.Reservation.Status.FULFILLED
            reservation.active_slot = None
            reservation.save(update_fields=["status", "active_slot"])

        _log_action(user, "issue.create", {"reader_id": reader.id, "copy_id": copy.id})

    return issue


def return_issue(issue_id, return_date=None, user=None):
    """Возврат экземпляра: выдача -> RETURNED, экземпляр -> AVAILABLE/RESERVED."""
    with transaction.atomic():
        # Сначала читаем book_id/copy_id без блокировки, затем Book -> BookCopy -> Issue.
        issue_info = (
            models.Issue.objects.filter(pk=issue_id)
            .values("copy__book_id", "copy_id")
            .first()
        )
        if issue_info is None:
            raise NotFound("Выдача не найдена.")
        book = _lock_book(issue_info["copy__book_id"])
        copy = _lock_copy(issue_info["copy_id"])
        try:
            issue = models.Issue.objects.select_for_update().select_related("reader").get(pk=issue_id)
        except models.Issue.DoesNotExist:
            raise NotFound("Выдача не найдена.")

        if issue.status != models.Issue.Status.ISSUED:
            raise Conflict("Возврат возможен только по активной выдаче.")

        now = return_date or timezone.now()
        issue.returned_at = now
        issue.status = models.Issue.Status.RETURNED
        issue.save(update_fields=["returned_at", "status"])

        copy.status = models.BookCopy.Status.AVAILABLE
        copy.save(update_fields=["status"])

        _promote_next(book, copy)

        _log_action(user, "issue.return", {"issue_id": issue.id, "copy_id": copy.id})

        return issue


def join_queue(reader_id, book_id, user=None):
    """Добавление читателя в конец очереди ожидания (бронь PENDING)."""
    with transaction.atomic():
        book = _lock_book(book_id)
        reader = _get_reader(reader_id)
        if reader.status != models.Reader.Status.ACTIVE:
            raise Conflict("Читатель не может встать в очередь (статус BLOCKED/SUSPENDED).")

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

        free_copy = (
            models.BookCopy.objects.select_for_update()
            .filter(book=book, status=models.BookCopy.Status.AVAILABLE)
            .order_by("id")
            .first()
        )
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
    with transaction.atomic():
        book_id = (
            models.Reservation.objects.filter(pk=reservation_id)
            .values_list("book_id", flat=True)
            .first()
        )
        if book_id is None:
            raise NotFound("Бронирование не найдено.")
        book = _lock_book(book_id)
        reservation = _lock_reservation(reservation_id)
        if reservation.status not in (
            models.Reservation.Status.PENDING,
            models.Reservation.Status.ACTIVE,
        ):
            raise Conflict("Отменить можно только активное или ожидающее бронирование.")

        copy = None
        if reservation.status == models.Reservation.Status.ACTIVE and reservation.copy_id:
            copy = _lock_copy(reservation.copy_id)
            if copy.status == models.BookCopy.Status.RESERVED:
                copy.status = models.BookCopy.Status.AVAILABLE
                copy.save(update_fields=["status"])

        _clear_reservation_slot(reservation)
        _promote_next(book, copy)

        _log_action(user, "reservation.cancel", {"reservation_id": reservation.id, "book_id": book.id})

        return reservation, copy


def _promote_next(book, available_copy):
    """Переход следующего читателя из очереди после освобождения экземпляра."""
    if available_copy is None:
        return None
    now = timezone.now()

    # Сначала блокируем экземпляр просроченного резерва, затем сами бронирования.
    stale = (
        models.Reservation.objects.filter(
            book=book,
            status=models.Reservation.Status.ACTIVE,
            expires_at__lt=now,
        )
        .order_by("queue_date", "id")
        .first()
    )
    stale_copy = None
    if stale is not None and stale.copy_id:
        stale_copy = _lock_copy(stale.copy_id)
    if stale is not None:
        if stale_copy is not None and stale_copy.status == models.BookCopy.Status.RESERVED:
            stale_copy.status = models.BookCopy.Status.AVAILABLE
            stale_copy.save(update_fields=["status"])
        stale = models.Reservation.objects.select_for_update().get(pk=stale.pk)
        stale.status = models.Reservation.Status.EXPIRED
        stale.active_slot = None
        stale.save(update_fields=["status", "active_slot"])

    next_reservation = (
        models.Reservation.objects.select_for_update()
        .filter(book=book, status=models.Reservation.Status.PENDING, active_slot=1)
        .order_by("queue_date", "id")
        .first()
    )
    if next_reservation is None:
        return None
    next_reservation.status = models.Reservation.Status.ACTIVE
    next_reservation.copy = available_copy
    next_reservation.expires_at = now + constants.RESERVATION_PERIOD
    next_reservation.save(update_fields=["status", "copy", "expires_at"])
    available_copy.status = models.BookCopy.Status.RESERVED
    available_copy.save(update_fields=["status"])
    return next_reservation


def expire_reservations(book=None):
    """Перевод просроченных резервов в статус EXPIRED и освобождение экземпляров."""
    with transaction.atomic():
        now = timezone.now()
        expired = models.Reservation.objects.filter(
            status=models.Reservation.Status.ACTIVE,
            expires_at__lt=now,
        )
        if book is not None:
            expired = expired.filter(book=book)
        rows = list(expired.order_by("book_id", "queue_date", "id"))
        if not rows:
            return []

        books = {
            item.id: item
            for item in models.Book.objects.select_for_update()
            .filter(pk__in={row.book_id for row in rows})
            .order_by("id")
        }
        copy_ids = {row.copy_id for row in rows if row.copy_id}
        copies = {
            item.id: item
            for item in models.BookCopy.objects.select_for_update()
            .filter(pk__in=copy_ids)
            .order_by("id")
        }
        reservations = {
            item.id: item
            for item in models.Reservation.objects.select_for_update()
            .filter(pk__in={row.id for row in rows})
            .order_by("book_id", "queue_date", "id")
        }

        processed = []
        for row in rows:
            reservation = reservations[row.id]
            copy = copies.get(reservation.copy_id)
            if copy is not None and copy.status == models.BookCopy.Status.RESERVED:
                copy.status = models.BookCopy.Status.AVAILABLE
                copy.save(update_fields=["status"])
            reservation.status = models.Reservation.Status.EXPIRED
            reservation.active_slot = None
            reservation.save(update_fields=["status", "active_slot"])
            _promote_next(books[reservation.book_id], copy)
            processed.append(reservation)
        return processed
