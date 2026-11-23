"""Бизнес-логика библиотеки: выдача, возврат, очередь, резервирование."""
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


def _get_copy(copy_id):
    try:
        return models.BookCopy.objects.select_for_update().select_related("book").get(pk=copy_id)
    except models.BookCopy.DoesNotExist:
        raise NotFound("Экземпляр книги не найден.")


def _get_reservation(reservation_id):
    try:
        return models.Reservation.objects.select_for_update().select_related("book").get(pk=reservation_id)
    except models.Reservation.DoesNotExist:
        raise NotFound("Бронирование не найдено.")


def issue_copy(reader_id, copy_id, user=None):
    """Выдача экземпляра читателю (в одной транзакции с изменением статуса)."""
    with transaction.atomic():
        reader = _get_reader(reader_id)
        if reader.status != models.Reader.Status.ACTIVE:
            raise Conflict("Читатель не может получать книги (статус BLOCKED/SUSPENDED).")

        copy = _get_copy(copy_id)
        reservation = None
        if copy.status == models.BookCopy.Status.RESERVED:
            reservation = (
                models.Reservation.objects.select_for_update()
                .filter(
                    reader=reader,
                    book=copy.book,
                    status=models.Reservation.Status.ACTIVE,
                )
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
            reservation.save(update_fields=["status"])

        _log_action(user, "issue.create", {"reader_id": reader.id, "copy_id": copy.id})

    return issue


def return_issue(issue_id, return_date=None, user=None):
    """Возврат экземпляра: выдача -> RETURNED, экземпляр -> AVAILABLE."""
    with transaction.atomic():
        try:
            issue = (
                models.Issue.objects.select_for_update()
                .select_related("copy", "reader")
                .get(pk=issue_id)
            )
        except models.Issue.DoesNotExist:
            raise NotFound("Выдача не найдена.")

        if issue.status != models.Issue.Status.ISSUED:
            raise Conflict("Возврат возможен только по активной выдаче.")

        now = return_date or timezone.now()
        issue.returned_at = now
        issue.status = models.Issue.Status.RETURNED
        issue.save(update_fields=["returned_at", "status"])

        copy = issue.copy
        copy.status = models.BookCopy.Status.AVAILABLE
        copy.save(update_fields=["status"])

        _promote_next(copy.book, copy)

        _log_action(user, "issue.return", {"issue_id": issue.id, "copy_id": copy.id})

        return issue


def join_queue(reader_id, book_id, user=None):
    """Добавление читателя в конец очереди ожидания (бронь PENDING)."""
    reader = _get_reader(reader_id)
    if reader.status != models.Reader.Status.ACTIVE:
        raise Conflict("Читатель не может встать в очередь (статус BLOCKED/SUSPENDED).")

    active_exists = (
        models.Reservation.objects.filter(
            reader=reader,
            book_id=book_id,
            status__in=[models.Reservation.Status.PENDING, models.Reservation.Status.ACTIVE],
        ).exists()
    )
    if active_exists:
        raise Conflict("Читатель уже находится в очереди ожидания на эту книгу.")

    reservation = models.Reservation.objects.create(
        reader=reader,
        book_id=book_id,
        status=models.Reservation.Status.PENDING,
        queue_date=timezone.now(),
        expires_at=timezone.now() + constants.RESERVATION_PERIOD,
    )

    _log_action(user, "queue.join", {"reader_id": reader.id, "book_id": book_id})

    return reservation


def cancel_reservation(reservation_id, user=None):
    """Отмена бронирования: освобождение экземпляра и продвижение очереди."""
    with transaction.atomic():
        reservation = _get_reservation(reservation_id)
        if reservation.status not in (
            models.Reservation.Status.PENDING,
            models.Reservation.Status.ACTIVE,
        ):
            raise Conflict("Отменить можно только активное или ожидающее бронирование.")

        was_active = reservation.status == models.Reservation.Status.ACTIVE
        reservation.status = models.Reservation.Status.CANCELLED
        reservation.save(update_fields=["status"])

        copy = None
        if was_active:
            copy = (
                models.BookCopy.objects.select_for_update()
                .filter(book=reservation.book, status=models.BookCopy.Status.RESERVED)
                .first()
            )
            if copy is not None:
                copy.status = models.BookCopy.Status.AVAILABLE
                copy.save(update_fields=["status"])

        _promote_next(reservation.book, copy)

        _log_action(user, "reservation.cancel", {"reservation_id": reservation.id, "book_id": reservation.book_id})

        return reservation, copy


def _promote_next(book, available_copy):
    """Переход следующего читателя из очереди после освобождения экземпляра."""
    if available_copy is None:
        return None
    now = timezone.now()
    stale = (
        models.Reservation.objects
        .select_for_update()
        .filter(
            book=book,
            status=models.Reservation.Status.ACTIVE,
            expires_at__lt=now,
        )
        .first()
    )
    if stale is not None:
        stale.status = models.Reservation.Status.EXPIRED
        stale.save(update_fields=["status"])
        stale_copy = (
            models.BookCopy.objects.select_for_update()
            .filter(book=book, status=models.BookCopy.Status.RESERVED)
            .first()
        )
        if stale_copy is not None:
            stale_copy.status = models.BookCopy.Status.AVAILABLE
            stale_copy.save(update_fields=["status"])

    next_reservation = (
        models.Reservation.objects
        .select_for_update()
        .filter(book=book, status=models.Reservation.Status.PENDING)
        .order_by("queue_date", "id")
        .first()
    )
    if next_reservation is None:
        return None
    next_reservation.status = models.Reservation.Status.ACTIVE
    next_reservation.expires_at = timezone.now() + constants.RESERVATION_PERIOD
    next_reservation.save(update_fields=["status", "expires_at"])
    available_copy.status = models.BookCopy.Status.RESERVED
    available_copy.save(update_fields=["status"])
    return next_reservation


def expire_reservations(book=None):
    """Перевод просроченных резервов в статус EXPIRED и освобождение экземпляров."""
    with transaction.atomic():
        now = timezone.now()
        expired = models.Reservation.objects.select_for_update().filter(
            status=models.Reservation.Status.ACTIVE,
            expires_at__lt=now,
        )
        if book is not None:
            expired = expired.filter(book=book)
        processed = []
        for reservation in expired.select_for_update():
            copy = (
                models.BookCopy.objects.select_for_update()
                .filter(book=reservation.book, status=models.BookCopy.Status.RESERVED)
                .first()
            )
            reservation.status = models.Reservation.Status.EXPIRED
            reservation.save(update_fields=["status"])
            if copy is not None:
                copy.status = models.BookCopy.Status.AVAILABLE
                copy.save(update_fields=["status"])
            _promote_next(reservation.book, copy)
            processed.append(reservation)
        return processed
