"""Изменения каталога с блокировками и проверками зависимостей."""
from django.db import transaction
from rest_framework.exceptions import NotFound

from library import models
from library.transitions import Conflict, change_status


def _lock_book(book_id):
    book = models.Book.objects.select_for_update().filter(pk=book_id).first()
    if book is None:
        raise NotFound("Книга не найдена.")
    return book


def _lock_copy_in_book(book_id, copy_id):
    book = _lock_book(book_id)
    copy = (
        models.BookCopy.objects.select_for_update()
        .filter(pk=copy_id, book=book)
        .first()
    )
    if copy is None:
        raise NotFound("Экземпляр книги не найден.")
    return book, copy


def update_copy(copy_id, *, user=None, inventory_number=None, status=None):
    """Обновить экземпляр; смена статуса идёт через карту переходов."""
    book_id = (
        models.BookCopy.objects.filter(pk=copy_id)
        .values_list("book_id", flat=True)
        .first()
    )
    if book_id is None:
        raise NotFound("Экземпляр книги не найден.")
    with transaction.atomic():
        _book, copy = _lock_copy_in_book(book_id, copy_id)
        if (
            inventory_number
            and models.BookCopy.objects.filter(inventory_number=inventory_number)
            .exclude(pk=copy.pk)
            .exists()
        ):
            raise Conflict("Инвентарный номер уже используется.")
        if status is not None and status != copy.status:
            if (
                status == models.BookCopy.Status.AVAILABLE
                and copy.status
                in (
                    models.BookCopy.Status.ISSUED,
                    models.BookCopy.Status.RESERVED,
                )
            ):
                raise Conflict(
                    "Возврат экземпляра в AVAILABLE выполняется только сервисами "
                    "выдачи и бронирования."
                )
            change_status(copy, status, user=user)
        if inventory_number and inventory_number != copy.inventory_number:
            copy.inventory_number = inventory_number
            copy.save(update_fields=["inventory_number"])
        return copy


def delete_copy(copy_id):
    """Удалить экземпляр, если по нему нет выдач."""
    book_id = (
        models.BookCopy.objects.filter(pk=copy_id)
        .values_list("book_id", flat=True)
        .first()
    )
    if book_id is None:
        raise NotFound("Экземпляр книги не найден.")
    with transaction.atomic():
        _book, copy = _lock_copy_in_book(book_id, copy_id)
        if models.Issue.objects.filter(copy=copy).exists():
            raise Conflict("Экземпляр участвует в выдачах и не может быть удалён.")
        live_reservations = list(
            models.Reservation.objects.select_for_update()
            .filter(
                copy=copy,
                status__in=[
                    models.Reservation.Status.PENDING,
                    models.Reservation.Status.ACTIVE,
                ],
            )
            .order_by("queue_date", "id")
        )
        if live_reservations:
            raise Conflict(
                "Экземпляр имеет активные бронирования и не может быть удалён."
            )
        copy.delete()


def delete_book(book_id):
    """Удалить книгу, если нет выдач и живых бронирований."""
    with transaction.atomic():
        book = _lock_book(book_id)
        # Фиксируем все экземпляры в порядке id перед проверкой зависимостей.
        list(
            models.BookCopy.objects.select_for_update()
            .filter(book=book)
            .order_by("id")
        )
        if models.Issue.objects.filter(copy__book=book).exists():
            raise Conflict("Книга имеет выдачи и не может быть удалена.")
        live_reservations = list(
            models.Reservation.objects.select_for_update()
            .filter(
                book=book,
                status__in=[
                    models.Reservation.Status.PENDING,
                    models.Reservation.Status.ACTIVE,
                ],
            )
            .order_by("queue_date", "id")
        )
        if live_reservations:
            raise Conflict("Книга имеет активные бронирования и не может быть удалена.")
        book.delete()
